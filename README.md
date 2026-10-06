# ZrLog API contracts

`zrlog-api` 是 ZrLog OpenAPI 3.1 契约的统一维护、索引和直接消费入口。

| 文件 | 用途 |
| --- | --- |
| [index.json](index.json) | 契约目录、版本、SHA-256、operationId、HTTP 方法和路径索引 |
| [admin-web.yaml](admin-web.yaml) | 后台文章、分类、上传和通知接口 |
| [blog-web.yaml](blog-web.yaml) | 博客公开只读接口 |

每份 YAML 都是独立、可直接加载的 OpenAPI 文件，只使用文档内部引用。索引中的 `file` 相对 `index.json` 所在目录解析；`id + operationId` 唯一标识一个操作。HTTP 参数、Schema、鉴权和 SSE 完成语义在 YAML 中维护，索引由 YAML 生成。

```sh
zrlogctl api --spec ../zrlog-api/admin-web.yaml list
zrlogctl api --spec ../zrlog-api/admin-web.yaml describe listArticles
zrlogctl api sources
```

仓库发布后，可直接下载 `https://raw.githubusercontent.com/zrlog/zrlog-api/main/index.json` 及其中的 YAML 文件。自动化集成应将 `main` 换成固定提交 SHA，并检查文件 SHA-256。目标站点由调用方配置，契约不会替调用方选择服务器。

## 维护与验证

```sh
python3 -m pip install -r requirements.txt
python3 bin/contracts.py index
python3 bin/contracts.py index --check
python3 bin/contracts.py sync --workspace ..
python3 bin/contracts.py sync --workspace .. --check
```

同步只覆盖已存在的消费仓库；可用 `--consumer zrlog-client-java` 等选项限制范围。客户端、官网及服务端文档中的 YAML 是生成快照，不独立维护。快照使各仓库可以独立、离线构建；发布前先提交本仓库的契约和索引，再同步并提交各消费者。

接口业务实现及兼容责任仍属于 `x-zrlog-owner-repository` 指向的服务端仓库。接口发生变化时，同时修改实现和这里的契约，运行服务端契约测试及客户端测试。OAuth 登录/刷新独立维护，内部 UI、插件私有接口不自动成为公开 API。

## 消费边界

- `zrlogctl`：通用 `api call` 和便捷命令共用 OpenAPI 请求构造、Schema 校验、鉴权、multipart 和 SSE 执行器。便捷命令保留分页、本地文件和发布状态校验。
- `zrlog-www`：从此目录同步，展示契约并导出原始 YAML、JSON 和机器可读索引。
- `zrlog-admin-web`、`zrlog-blog-web-parent`：保留生成快照，检查契约与 Controller/DTO 的一致性。
- 本仓库不包含 Java 业务接口层、不生成 SDK，也不引入服务端运行时依赖。
