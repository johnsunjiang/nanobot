# deploy

部署文件的占位目录。这一步没有 Compose，没有 Dockerfile，也没有配置模板。

真正的 `config.template.json` 放到 D4，并且要先改计划 §5.1：当前 nanobot 在解析 `${ENV}` 之前就做类型和枚举校验，所以带类型的字段不能一律写成 `${ENV}`。

- 生产 Compose、维护模式 Compose、镜像构建和备份脚本以后再加。
- 服务器上的密钥不进这个仓库。
- 本目录里一旦出现 JSON，CI 的 `config-lint` 会检查它能被解析，并且名字里带 key、secret、token、password 的字段值必须正好是 `${VAR}`。文件名里带 `config` 的 JSON 还会用 nanobot 真正加载一次。
