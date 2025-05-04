# IndexTTS API 接口文档

## 基本信息

- 基础URL: `http://your-domain:port/api/tts`
- 接口协议: HTTP/HTTPS
- 数据格式: JSON

## 接口列表

### 1. 获取可用参考音频列表

获取系统中所有可用的参考音频文件。

- **接口**: `/api/tts/prompts`
- **方法**: GET
- **响应示例**:
```json
{
    "prompts": [
        "male_1.wav",
        "female_1.wav",
        "child_1.wav"
    ]
}
```

### 2. 创建语音生成任务

创建一个新的语音生成任务。

- **接口**: `/api/tts/tasks`
- **方法**: POST
- **请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| text | string | 是 | 需要转换的文本内容 |
| output_path | string | 是 | 生成音频的保存目录路径 |
| infer_mode | string | 否 | 推理模式，可选值："普通推理"(默认)/"批次推理" |

- **请求示例**:
```json
{
    "text": "你好，这是一段测试文本",
    "output_path": "/path/to/output/directory",
    "infer_mode": "普通推理"
}
```

- **响应示例**:
```json
{
    "task_id": "task_1709123456_0",
    "status": "pending"
}
```

### 3. 查询任务状态

查询指定任务的处理状态。

- **接口**: `/api/tts/tasks/{task_id}`
- **方法**: GET
- **路径参数**:
  - task_id: 任务ID（创建任务时返回的ID）

- **响应参数**:

| 参数名 | 类型 | 描述 |
|--------|------|------|
| task_id | string | 任务ID |
| status | string | 任务状态：pending(等待处理)/processing(处理中)/completed(已完成)/failed(失败) |
| output_path | string | 输出文件目录路径 |
| process_time | number | 处理耗时(秒)，仅在任务完成或失败时返回 |
| error | string | 错误信息，仅在任务失败时返回 |

- **响应示例**:

成功时：
```json
{
    "task_id": "task_1709123456_0",
    "status": "completed",
    "output_path": "/path/to/output/directory",
    "process_time": 5.23
}
```

失败时：
```json
{
    "task_id": "task_1709123456_0",
    "status": "failed",
    "output_path": "/path/to/output/directory",
    "process_time": 2.15,
    "error": "生成失败的具体原因"
}
```

### 4. 健康检查

检查服务是否正常运行。

- **接口**: `/health`
- **方法**: GET
- **响应示例**:
```json
{
    "status": "ok"
}
```

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误（如参考音频不存在） |
| 404 | 资源不存在（如任务ID不存在） |
| 500 | 服务器内部错误 |

## 使用建议

1. 调用流程：
   - 首先通过 `/api/tts/prompts` 获取可用的参考音频列表
   - 使用 `/api/tts/tasks` 创建语音生成任务
   - 定期通过 `/api/tts/tasks/{task_id}` 查询任务状态
   - 当状态为 "completed" 时，从 output_path 获取生成的音频文件

2. 注意事项：
   - 建议对任务状态查询设置合理的轮询间隔（建议3-5秒）
   - output_path 需要确保目录具有写入权限
   - 参考音频文件名需要使用 `/api/tts/prompts` 接口返回的值
   - 任务状态信息会在服务重启后丢失，请及时保存任务ID和状态
