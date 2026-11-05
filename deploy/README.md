# deploy

部署文件的占位目录。这一步只有配置模板，没有 Compose，也没有 Dockerfile。

- `config.template.json`：叶子值都是 `${ENV}` 占位符，没有真实密钥、地址或账号。
- 生产 Compose、维护模式 Compose、镜像构建和备份脚本以后再加。
- 服务器上的密钥不进这个仓库。
