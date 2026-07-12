# 后端测试入口

后端测试位于 `backend/tests/`。安装与运行命令、测试分层和安全回归矩阵统一维护在 [`../docs/testing.md`](../docs/testing.md)。

快速运行：

```bash
python -m pip install -r backend/requirements-dev.txt
pytest -q backend/tests
python -m compileall -q backend
```
