# OKX 自动交易系统

一个基于 Python 的 OKX 自动交易系统，支持通过 TradingView 信号自动执行交易。

## 功能特点

- 支持现货交易
- 支持限价单和市价单
- 支持多交易对配置
- 支持域名和 HTTPS 
- 集成企业微信通知
- 自动SSL证书申请
- 完整的日志记录

## 前置条件
- Ubuntu 20.04/CentOS 7 或更高版本
- Python 3.10.9 或更高版本
- 已解析的域名（指向服务器IP）
- root 权限

## Python 环境配置
1. 登录服务器
```bash
ssh root@你的服务器IP
```
### Ubuntu/Debian 系统:
2. 一键安装python命令，如何不成功可以选择下面的命令手动安装
```bash
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y && sudo apt clean && \sudo apt install -y software-properties-common && \sudo add-apt-repository -y ppa:deadsnakes/ppa && \sudo apt update && \sudo apt install -y python3.10 python3.10-venv python3.10-dev && \sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
```
3. 按照下面的命令逐条复制安装python
```bash
# 一键更新升级系统
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y && sudo apt clean

# 安装依赖
sudo apt install -y software-properties-common

# 添加 deadsnakes PPA 源
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# 安装 Python 3.10
sudo apt install -y python3.10 python3.10-venv python3.10-dev

# 设置 Python 3.10 为默认版本
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
```

### CentOS 系统:
```bash
# 一键更新升级系统
sudo yum update -y && sudo yum upgrade -y && sudo yum clean all

# 安装依赖
sudo yum groupinstall -y "Development Tools"
sudo yum install -y openssl-devel bzip2-devel libffi-devel

# 下载并编译 Python 3.10.9
wget https://www.python.org/ftp/python/3.10.9/Python-3.10.9.tgz
tar xzf Python-3.10.9.tgz
cd Python-3.10.9
./configure --enable-optimizations
sudo make altinstall

# 创建软链接
sudo ln -sf /usr/local/bin/python3.10 /usr/bin/python3
sudo ln -sf /usr/local/bin/pip3.10 /usr/bin/pip3

# 清理安装文件
cd ..
rm -rf Python-3.10.9*
```

## 快速部署

### 1. 一键安装程序脚本自动安装
```bash
wget https://raw.githubusercontent.com/jiabo09683/okxdjtv/main/deploy.sh && \chmod +x deploy.sh && \./deploy.sh
```

### 2. 配置说明

部署过程中需要输入：
- 域名地址
- 选择是否自动配置证书（自动配置证书需要80端口，可以自己上传证书到服务器，然后提供路径）
- 环境变量配置（可选择N稍后配置）

### 3. 环境变量配置
国外服务器不需要配置代理
 `.env` 文件，配置以下参数：

```properties
# OKX API 配置
API_KEY=你的API密钥
SECRET=你的API密钥
PASSWORD=你的API密码

# 交易配置
TRADE_TYPE=spot             # 交易类型：spot=现货
BUY_ORDER_TYPE=limit        # 买入订单类型：limit=限价单/market=市价单
SELL_ORDER_TYPE=market      # 卖出订单类型：limit=限价单/market=市价单
TRADE_SYMBOLS=ETH/USDT,BTC/USDT  # 交易对,多个用逗号分隔

# 域名设置
USE_DOMAIN=true            # true=使用域名, false=使用IP
DOMAIN_NAME=your.domain.com  #填写解析的域名
USE_HTTPS=true            # 是否启用HTTPS

# 通知设置
WECHAT_BOT_URL=你的企业微信机器人webhook地址
```

## 部署后验证

1. 检查服务状态:
```bash
supervisorctl status okxdjtv
```

2. 检查SSL证书:
```bash
curl https://你的域名
```

3. 查看运行日志:
```bash
tail -f /var/log/okxdjtv/out.log
```

## 使用说明

### TradingView 警报配置

1.在 TradingView 警报中设置企业微信接收到的消息,消息格式如下:

```json
{
  "ticker": "{{ticker}}",
  "exchange": "okx",
  "action": "{{strategy.order.action}}",
  "amount": "{{strategy.order.contracts}}",
  "price": "{{strategy.order.price}}", 
  "symbol": "BTC/USDT（币种名字在env文件配置后自动生成）",
  "secret": "你的密钥（由系统自动生成）",
  "time": "{{time}}",
  "interval": "{{interval}}"
}
```

2. 在 TradingView 警报中设置企业微信接收到的Webhook URL 链接格式如下：
```
 https//域名/webhook
```


## 常用维护命令

### 服务管理
```bash
# 重新加载配置
supervisorctl reread
supervisorctl update

# 重启服务
supervisorctl restart okxdjtv

# 停止服务
supervisorctl stop okxdjtv

# 启动服务
supervisorctl start okxdjtv
```

### 日志查看
```bash
# 查看程序输出
tail -f /var/log/okxdjtv/out.log

# 查看错误日志
tail -f /var/log/okxdjtv/err.log
```

## 常见问题

### Python 版本问题
如果遇到 Python 版本相关错误，请确保：
1. Python 版本 >= 3.10.9
2. pip 已正确安装
3. 虚拟环境使用正确的 Python 版本

检查方法：
```bash
# 检查 Python 版本
python3 --version

# 检查 pip 版本
pip3 --version

# 检查虚拟环境 Python 版本
source venv/bin/activate
python --version
```

### SSL证书问题
1. 确保域名已正确解析到服务器IP
2. 检查证书文件权限和路径
3. 确认80和443端口未被占用

### 服务启动问题
1. 检查环境变量配置
2. 查看错误日志
3. 确认Python依赖安装完整

## 安全建议

1. 使用强密码和复杂的 API 密钥
2. 定期更新系统和依赖包
3. 使用 HTTPS 和 SSL 证书
4. 配置防火墙限制访问
5. 定期备份配置文件

## License

MIT License

## 联系方式

如有问题，请提交 Issue 或 Pull Request。