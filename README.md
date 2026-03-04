# MinerU 在线 API 解析功能说明

得益于Mineru出色的PDF解析能力，在实际生产中如果使用了RAGFLOW来管理知识库，会需要测试Mineru解析器,但是官方只提供了Http或者MCP请求本地部署的Mineru，Mineru的VLM解析也需要一定的算力，繁琐的部署和硬件成本会给想尝试Mineru解析器的开发者造成一定的阻碍，而mineru提供了免费的额度可以调用官网的API来进行解析，所以开发这个插件。项目已支持调用 MinerU 官方开源社区提供的在线 API（Online API）进行文档解析。使用该功能可以免除繁琐的本地 MinerU 环境部署，直接调用官网API高效地完成 PDF 和其他复杂文档的智能解析。

## 原理
原理是使用官网的api调用上传文档进行解析，下载解析的zip包到本地，Zip包里包含了mineru解析结果，通过content_list.json文件得到解析的type、text、text_level、bbox、page_idx等信息，接入到Ragflow目前支持的Mineru解析器中。对于VLM解析模式对复杂表格的PDF完成效果出色，但是解析得到json结果是扁平化处理过的，即没有像Pipeline模式将文档的多级结构信息保留下来，所以需要对扁平化的结果进行一定量的合并处理，否则直接接入Ragflow会导致大量的文档块碎片化，影响检索效果，这个需要开发者根据实际情况进行改造，本插件是进行了简单的Token大小判断进行合并。


## 如何启动与使用

在启动使用在线 API 解析前，只需要修改配置文件即可，之后按您正常的方式启动 RAGFlow 服务（如 `docker compose up -d` 或通过 Python 启动服务脚本）。服务在进行文档解析时，若匹配到使用 MinerU，将自动调用在线接口。

启动配置说明如下：

1. **定位配置文件**：找到配置文件 `\ragflow\conf\service_conf_back.yaml`,并重命名为service_conf.yaml
2. **启用在线模式**：在 `mineru` 配置块中，确保将 `online_enabled` 设为 `true`。
3. **设置请求凭证**：填写由 MinerU 官方获取的 API 授权 `token`。

## 详细参数配置

有关 MinerU 解析过程相关的详细参数（例如轮询间隔 `poll_interval`、超时时间 `poll_timeout`、临时使用目录 `temp_dir` 等）都已标出。

**详细参数请详见 `ragflow\conf\service_conf_back.yaml` 的 `mineru` 配置块**。您可根据部署机器的网络情况、并发程度和存储需求进行针对性调整。
