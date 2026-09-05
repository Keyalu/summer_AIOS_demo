# Mock 实现说明

## 一、什么是 Mock

Mock（模拟对象）是一种测试和开发技术：用一个接口相同的"假对象"替代真实对象，在某些条件下返回预设的固定数据，从而让依赖方可以独立开发。

### 1.1 为什么分组四需要 Mock

五个组并行开发，组3（AppAgent）的逻辑需要在组4（Tools）完成之前就开始编码。如果没有 Mock，组3要么干等组4实现完，要么自己写死一份假数据进行开发。Mock 解决了这个鸡生蛋蛋生鸡的问题：

```
开发期
  组3 AppAgent → 调用 MockToolRegistry → 拿到模拟数据 → 继续开发 ✓

集成期
  组3 AppAgent → 调用 ToolRegistry（真实）→ 执行真实文件操作 → 集成 ✓

切换成本
  MockToolRegistry → ToolRegistry  （仅 import 一行代码）
```

### 1.2 任务书要求

任务书明确要求分组四交付 Mock 实现，占 **5 分**：

> "MCP Mock Mock 实现"

Mock 是六个评分项之一，要求提供一组带有预设工具的模拟版本供其他组使用。

---

## 二、Mock 实现清单

分组四需要提供两个 Mock 组件：

| Mock 组件 | 对应的真实实现 | 文件 | 用途 |
|-----------|---------------|------|------|
| MockToolRegistry | ToolRegistry | src/mock_registry.py | 供组3调用，不执行真实 OS 操作 |
| MockSkillLibrary | SkillLibrary | src/mock_skills.py | 供组3调用，返回模拟技能结果 |
| MCP JSON-RPC Mock | MCPConnector | src/mcp_connector.py | 模拟 MCP 协议 JSON-RPC 格式 |

---

## 三、实现原理

### 3.1 核心思想：接口不变，行为替换

Mock 和真实实现继承同一个抽象接口：

```
IToolRegistry (ABC)
├── register(name, func, schema)   ← 需要实现
├── unregister(name)               ← 需要实现
├── call(name, params)             ← 需要实现（★ MOCK 在这里分支）
├── list_tools()                   ← 需要实现
└── has(name)                      ← 需要实现

真实实现: ToolRegistry → call() → shutil.copy2() / subprocess.run()
Mock 实现: MockToolRegistry → call() → 直接返回 "{'success': True, 'result': '模拟'}"
```

### 3.2 层叠架构

```
组3 AppAgent
    │
    ▼
IToolRegistry 接口（ABI 稳定层）
    │
    ├────── ToolRegistry     （真实实现，操作 shutil / subprocess）
    │
    └────── MockToolRegistry （Mock 实现，返回固定模拟数据）
```

组3的代码只依赖 `IToolRegistry` 接口，不关心底层是真实还是 Mock。

---

## 四、MockToolRegistry 详细设计

### 4.1 预置工具

MockToolRegistry 初始化时预置 8 个工具的 schema：

| 工具名 | 功能说明 | 参数 |
|--------|---------|------|
| copy_file | 复制文件（Mock：不执行真实复制） | src, dest |
| move_file | 移动文件（Mock：不执行真实移动） | src, dest |
| delete_file | 删除文件（Mock：不执行真实删除） | path |
| create_folder | 创建文件夹（Mock：不执行真实创建） | path |
| list_directory | 列出目录（Mock：返回模拟列表） | path |
| read_file | 读取文件（Mock：返回模拟内容） | path |
| write_file | 写入文件（Mock：不执行真实写入） | path, content |
| run_command | 执行系统命令（Mock：不执行真实命令） | cmd |

### 4.2 call() 方法 —— Mock 的核心行为

```python
def call(self, name: str, params=None, user_level=None) -> ToolResult:
    """Mock 调用：不执行真实 OS 操作，直接返回模拟成功。"""
    if name not in self._tools:
        return ToolResult.fail(f"工具未注册: {name}")

    # ★ 关键：不调用真实工具函数，直接返回模拟数据
    return ToolResult.ok(
        result=f"[Mock] {name} 执行成功（模拟）— 参数: {params}"
    )
```

### 4.3 完整代码

```python
class MockToolRegistry(IToolRegistry):
    """Mock 工具注册表。供组3在组4完成之前使用。"""

    def __init__(self):
        self._tools = {}
        self._schemas = {}
        self._register_defaults()

    def register(self, name, func, schema=None):
        self._tools[name] = func
        if schema:
            self._schemas[name] = schema

    def unregister(self, name):
        return self._tools.pop(name, None) is not None

    def call(self, name, params=None, user_level=None):
        params = params or {}
        if name not in self._tools:
            return ToolResult.fail(f"工具未注册: {name}")
        return ToolResult.ok(
            result=f"[Mock] {name} 执行成功（模拟）— 参数: {params}"
        )

    def list_tools(self):
        return list(self._schemas.values())

    def has(self, name):
        return name in self._tools

    def _register_defaults(self):
        """注册 8 个预置默认工具的 Mock 版本。"""
        defaults = [
            ("copy_file", "复制文件", ["src", "dest"]),
            ("move_file", "移动文件", ["src", "dest"]),
            ("delete_file", "删除文件", ["path"]),
            ("create_folder", "创建文件夹", ["path"]),
            ("list_directory", "列出目录", ["path"]),
            ("read_file", "读取文件", ["path"]),
            ("write_file", "写入文件", ["path", "content"]),
            ("run_command", "执行系统命令", ["cmd"]),
        ]
        for name, desc, params in defaults:
            self.register(name, lambda **kw: {"success": True}, ToolSchema(
                name=name, description=f"{desc}（Mock）",
                parameters=[ToolParam(p, ToolParamType.STRING, f"参数: {p}") for p in params]
            ))
```

---

## 五、MockSkillLibrary 详细设计

### 5.1 预置技能

MockSkillLibrary 初始化时预置 8 个技能的 schema：

| 技能名 | 功能说明 | 模拟摘要 |
|--------|---------|---------|
| organize_downloads | 整理下载目录 | "整理完成：文档 5 个，图片 12 个" |
| system_check | 系统状态检查 | "磁盘使用率 65%，内存使用 4.2/8.0GB" |
| find_files | 搜索文件 | "找到 8 个匹配文件" |
| cleanup_temp | 清理临时文件 | "删除临时文件 23 个，释放 156MB" |
| backup_directory | 目录备份 | "备份完成：已压缩为 zip 文件" |
| find_large_files | 查找大文件 | "找到 5 个大于 100MB 的文件" |
| find_duplicate_files | 查找重复文件 | "找到 2 组重复文件，共 6 个文件" |
| disk_usage | 磁盘使用 | "磁盘使用率 65%，剩余 120GB" |

### 5.2 call_skill() 方法

```python
def call_skill(self, name, params=None):
    """Mock 调用：返回模拟成功结果。"""
    params = params or {}
    if name not in self._skills:
        return ToolResult.fail(f"Skill 未注册: {name}")
    return ToolResult.ok(
        result={
            "skill": name,
            "status": "[Mock] 模拟执行成功",
            "params": params,
            "summary": self._mock_summary(name, params),  # 不同技能返回不同摘要
        }
    )
```

### 5.3 模拟摘要字典

每个技能返回不同的模拟摘要，让组3看到的反馈是有针对性的：

```python
SUMMARIES = {
    "organize_downloads":    "整理完成：文档 5 个，图片 12 个，视频 3 个，其他 2 个",
    "system_check":          "磁盘使用率 65%，内存使用 4.2/8.0 GB，运行进程 128 个",
    "find_files":            "找到 8 个匹配文件",
    "cleanup_temp":          "清理完成：删除临时文件 23 个，释放空间 156 MB",
    "backup_directory":      "备份完成：已压缩为 zip 文件",
    "find_large_files":      "找到 5 个大于 100MB 的文件",
    "find_duplicate_files":  "找到 2 组重复文件，共 6 个文件",
    "disk_usage":            "磁盘使用率 65%，剩余 120 GB",
}
```

---

## 六、MCP JSON-RPC 2.0 Mock

### 6.1 为什么需要 JSON-RPC Mock

MCP 协议基于 JSON-RPC 2.0 传输。即使后端是 Mock 实现，前端（组3）仍需要按 JSON-RPC 2.0 标准格式通信，为后续接入真实 MCP Server 做好准备。

### 6.2 请求/响应格式

```python
def mock_jsonrpc_call(registry, tool_name, params):
    """以 JSON-RPC 2.0 格式返回模拟调用结果。"""
    result = registry.call(tool_name, params)
    request_id = random.randint(1, 100000)

    if result.success:
        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": result.result}]
            },
            "id": request_id,
        }
    else:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,    # Internal error
                "message": result.error,
            },
            "id": request_id,
        }
```

### 6.3 响应示例

**成功响应：**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Mock 天气: 北京 晴转多云, 18°C~28°C, 空气质量良"
      }
    ]
  },
  "id": 41283
}
```

**失败响应：**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "工具未注册: unknown_tool"
  },
  "id": 41284
}
```

---

## 七、组3如何使用 Mock

### 7.1 导入 Mock

```python
# 开发期：引入 Mock
from src import MockToolRegistry, MockSkillLibrary

registry = MockToolRegistry()
skills = MockSkillLibrary(registry)
```

### 7.2 调用 Mock 工具

```python
# 组3调用工具，拿到模拟结果
result = registry.call("copy_file", {"src": "/home/a.txt", "dest": "/tmp/a.txt"})
print(result.to_dict())
# → {"success": True, "result": "[Mock] copy_file 执行成功（模拟）— 参数: {'src': '/home/a.txt', 'dest': '/tmp/a.txt'}"}
```

### 7.3 切换到真实实现

```python
# 集成期：把 Mock 替换为真实实现
# 只需要改一行 import！其余代码完全不变

# 开发期
from src import MockToolRegistry      # ← 删除这行
registry = MockToolRegistry()          # ← 删除这行

# 集成期
from src import ToolRegistry           # ← 替换为这行
registry = ToolRegistry()              # ← 替换为这行

# 其余所有逻辑保持不变
result = registry.call("copy_file", {"src": "...", "dest": "..."})
# 现在执行的是真实的 shutil.copy2()
```

---

## 八、Mock vs 真实实现对比

| 维度 | MockToolRegistry | ToolRegistry（真实） |
|------|-----------------|---------------------|
| 接口 | IToolRegistry | IToolRegistry |
| 注册工具 | ✅ register() | ✅ register() |
| 注销工具 | ✅ unregister() | ✅ unregister() |
| 列出工具 | ✅ list_tools() | ✅ list_tools() |
| 调用工具 | ✅ call() → 返回模拟 | ✅ call() → 执行真实操作 |
| 权限校验 | ❌ Mock 不校验 | ✅ 三级权限检查 |
| 调用统计 | ❌ Mock 不统计 | ✅ stats.record() |
| 文件操作 | ❌ 不执行真实 copy/move/delete | ✅ shutil.copy2() 等 |
| 命令执行 | ❌ 不执行真实 subprocess | ✅ subprocess.run() |
| 适用阶段 | 开发期、测试期 | 集成期、演示期 |

---

## 九、测试验证

### 9.1 Mock 测试

```python
class TestMockImplementations:
    def test_mock_registry(self):
        reg = MockToolRegistry()
        assert reg.has("copy_file")
        r = reg.call("copy_file", {"src": "/a", "dest": "/b"})
        assert r.success is True
        assert "[Mock]" in r.result

    def test_mock_skills(self):
        skills = MockSkillLibrary()
        r = skills.call_skill("organize_downloads")
        assert r.success is True
        assert r.result["status"] == "[Mock] 模拟执行成功"

    def test_mock_unregistered_tool(self):
        reg = MockToolRegistry()
        r = reg.call("nonexistent", {})
        assert r.success is False
        assert "未注册" in r.error
```

### 9.2 测试结果

```
tests/test_all.py::TestMockImplementations::test_mock_registry PASSED
tests/test_all.py::TestMockImplementations::test_mock_skills      PASSED
```

Mock 相关测试全部通过（Windows + WSL Ubuntu 双平台）。

---

## 十、Mock 设计原则总结

| 原则 | 说明 |
|------|------|
| 接口一致性 | Mock 和真实实现共享同一接口，能无缝切换 |
| 最小信息量 | Mock 返回的信息足够组3判断逻辑正确性，但不提供多余细节 |
| 零副作用 | Mock 不触碰文件系统、不创建进程、不修改系统状态 |
| 可组合 | Mock 的工具可以像真实工具一样被组合调用 |
| 自描述 | 返回值明确标注 `[Mock]`，防止误用 |
