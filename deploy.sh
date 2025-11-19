#!/bin/bash

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用root权限运行此脚本"
    exit 1
fi

# 获取域名输入
read -p "请输入您的域名(例如: trade.yourdomain.com): " DOMAIN
EMAIL="admin@${DOMAIN}"
echo "已自动生成邮箱: $EMAIL"

# 更新系统并安装必要的包
if [ -f /etc/debian_version ]; then
    # Debian/Ubuntu系统
    apt update && apt upgrade -y
    apt install -y python3 python3-pip git supervisor nginx certbot python3-certbot-nginx
elif [ -f /etc/redhat-release ]; then
    # CentOS系统
    yum update -y
    yum install -y epel-release
    yum install -y python3 python3-pip git supervisor nginx certbot python3-certbot-nginx
fi

# 添加证书配置选项
read -p "是否自动申请SSL证书? (y/n): " AUTO_SSL
if [[ $AUTO_SSL =~ ^[Yy]$ ]]; then
    # 原有的自动申请证书流程
    echo "创建证书验证目录..."
    mkdir -p /var/www/html/.well-known/acme-challenge
    chmod -R 755 /var/www/html
    
    echo "申请 SSL 证书..."
    certbot certonly --webroot -w /var/www/html -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email --non-interactive
    
    if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        echo "SSL 证书申请失败!"
        exit 1
    fi
    
    SSL_CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    SSL_KEY="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
else
    # 手动配置证书路径
    read -p "请输入SSL证书路径 (fullchain.pem): " SSL_CERT
    read -p "请输入SSL私钥路径 (privkey.pem): " SSL_KEY
    
    if [ ! -f "$SSL_CERT" ] || [ ! -f "$SSL_KEY" ]; then
        echo "证书文件不存在!"
        exit 1
    fi
fi

# 检查必要服务状态
echo "检查服务状态..."
systemctl start supervisor
systemctl start nginx

if ! systemctl is-active --quiet nginx; then
    echo "Nginx 启动失败"
    exit 1
fi

if ! systemctl is-active --quiet supervisor; then
    echo "Supervisor 启动失败"
    exit 1
fi

# 克隆项目
if [ -d "/root/okxdjtv" ]; then
    echo "检测到已存在项目目录，正在备份..."
    mv /root/okxdjtv "/root/okxdjtv_backup_$(date +%Y%m%d_%H%M%S)"
fi

git clone https://github.com/jiabo09683/okxdjtv.git /root/okxdjtv
cd /root/okxdjtv

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
echo "检测到需要配置环境变量..."
read -p "是否现在编辑 .env 文件? (y/n): " EDIT_ENV
if [[ $EDIT_ENV =~ ^[Yy]$ ]]; then
    nano .env
    SKIP_SERVICE_START=0
else
    echo "跳过环境变量配置..."
    SKIP_SERVICE_START=1
fi

# 创建日志目录
mkdir -p /var/log/okxdjtv
chmod 755 /var/log/okxdjtv

# 配置 Supervisor
echo "配置 Supervisor..."
cat > /etc/supervisor/conf.d/okxdjtv.conf << EOF
[program:okxdjtv]
directory=/root/okxdjtv
command=/root/okxdjtv/venv/bin/python /root/okxdjtv/okx_account.py
user=root
autostart=$([ "$SKIP_SERVICE_START" == "1" ] && echo "false" || echo "true")
autorestart=true
startsecs=10
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/okxdjtv/err.log
stdout_logfile=/var/log/okxdjtv/out.log
environment=PATH="/root/okxdjtv/venv/bin:%(ENV_PATH)s",PYTHONPATH="/root/okxdjtv"
EOF

# 重新加载 Supervisor 配置
supervisorctl reread
supervisorctl update

# 创建证书验证目录
echo "创建证书验证目录..."
mkdir -p /var/www/html/.well-known/acme-challenge
chmod -R 755 /var/www/html

# 配置基础的 Nginx (仅 HTTP)
echo "配置基础 HTTP 服务..."
cat > /etc/nginx/conf.d/$DOMAIN.conf << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# 测试并重启 Nginx
echo "测试 Nginx 配置..."
if ! nginx -t; then
    echo "Nginx 配置测试失败"
    exit 1
fi
systemctl restart nginx

# 修改 Nginx HTTPS 配置部分
cat > /etc/nginx/conf.d/$DOMAIN.conf << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name $DOMAIN;
    
    ssl_certificate $SSL_CERT;
    ssl_certificate_key $SSL_KEY;
    
    # SSL 配置优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# 再次测试并重启 Nginx
if ! nginx -t; then
    echo "HTTPS 配置失败"
    exit 1
fi
systemctl restart nginx

# 配置证书自动续期
echo "配置自动续期..."
cat > /etc/cron.d/certbot-renewal << EOF
0 0,12 * * * root test -x /usr/bin/certbot -a \! -d /run/systemd/shutdown && certbot renew --quiet --deploy-hook "systemctl reload nginx"
EOF
chmod 644 /etc/cron.d/certbot-renewal

if [ "$SKIP_SERVICE_START" != "1" ]; then
    # 启动服务
    echo "启动服务..."
    supervisorctl start okxdjtv

    # 等待服务启动
    sleep 5
    if ! supervisorctl status okxdjtv | grep -q "RUNNING"; then
        echo "服务启动失败，请检查以下信息："
        echo "1. Supervisor 状态："
        supervisorctl status
        echo "2. 错误日志："
        tail -n 20 /var/log/okxdjtv/err.log
        exit 1
    fi
    
    # 显示完整部署信息
    echo "=================== 部署完成 ==================="
    echo "项目目录: /root/okxdjtv"
    echo "域名: $DOMAIN"
    echo "SSL证书路径: /etc/letsencrypt/live/$DOMAIN/"
    echo "日志文件位置:"
    echo "  - 程序输出: /var/log/okxdjtv/out.log"
    echo "  - 错误日志: /var/log/okxdjtv/err.log"
    echo "常用命令:"
    echo "  - 查看状态: supervisorctl status okxdjtv"
    echo "  - 重启服务: supervisorctl restart okxdjtv"
    echo "  - 查看日志: tail -f /var/log/okxdjtv/out.log"
    echo "=============================================="
else
    # 显示待配置信息
    echo "=================== 部署完成 ==================="
    echo "项目目录: /root/okxdjtv"
    echo "域名: $DOMAIN"
    echo "SSL证书路径: /etc/letsencrypt/live/$DOMAIN/"
    echo "环境变量文件: /root/okxdjtv/.env (需要配置)"
    echo ""
    echo "后续步骤:"
    echo "1. 编辑环境变量: nano /root/okxdjtv/.env"
    echo "2. 重新加载 Supervisor:"

    echo "3. 启动服务: supervisorctl start okxdjtv"
    echo "4. 检查状态: supervisorctl status okxdjtv"
    echo "5. 查看日志:"
    echo "   - 程序日志: tail -f /var/log/okxdjtv/out.log"
    echo "   - 错误日志: tail -f /var/log/okxdjtv/err.log"
    echo "常用命令:"
    echo "  - 重新加载 Supervisor:"
    echo "  - supervisorctl reread"
    echo "  - supervisorctl update"
    echo "  - 启动服务: supervisorctl start okxdjtv"
    echo "  - 停止服务：supervisorctl stop okxdjtv"
    echo "  - 重启服务: supervisorctl restart okxdjtv"
    echo "  - 查看状态: supervisorctl status okxdjtv"

    echo "=============================================="
fi

# 显示服务状态
echo "Nginx 状态:"
systemctl status nginx | grep "Active:"
echo "Supervisor 状态:"
systemctl status supervisor | grep "Active:"
