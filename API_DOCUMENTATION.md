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

### 4. 创建批量语音生成任务

创建一个批量语音生成任务，可以同时处理多个文本到语音的转换。

- **接口**: `/api/tts/batch_tasks`
- **方法**: POST
- **请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| output_directory | string | 是 | 所有生成音频的保存目录路径 |
| speeches | object | 是 | 文件名到文本内容的映射，键为文件名(必须以.wav结尾)，值为要转换的文本 |
| prompt_path | string | 否 | 指定使用的参考音频文件路径，不指定则随机选择 |
| infer_mode | string | 否 | 推理模式，可选值："普通推理"(默认)/"批次推理" |

- **请求示例**:
```json
{
    "output_directory": "/path/to/output/directory",
    "speeches": {
        "file1.wav": "这是第一段测试文本",
        "file2.wav": "这是第二段测试文本",
        "file3.wav": "这是第三段测试文本"
    },
    "prompt_path": "male_1.wav",
    "infer_mode": "普通推理"
}
```

- **响应示例**:
```json
{
    "task_id": "batch_1709123456_0",
    "status": "pending",
    "total_files": 3
}
```

### 5. 查询批量任务状态

查询批量任务的处理状态。使用与普通任务相同的接口，但返回不同的响应结构。

- **接口**: `/api/tts/tasks/{task_id}`
- **方法**: GET
- **路径参数**:
  - task_id: 任务ID（创建批量任务时返回的ID）

- **响应参数**:

| 参数名 | 类型 | 描述 |
|--------|------|------|
| task_id | string | 任务ID |
| status | string | 任务状态：pending(等待处理)/processing(处理中)/completed(已完成)/failed(失败) |
| output_directory | string | 输出目录路径 |
| total_files | number | 总文件数 |
| processed_files | number | 已处理的文件数 |
| process_time | number | 处理耗时(秒)，仅在任务完成或失败时返回 |
| errors | array | 错误信息列表，包含失败文件的信息，仅在有错误时返回 |

- **响应示例**:

处理中：
```json
{
    "task_id": "batch_1709123456_0",
    "status": "processing",
    "output_directory": "/path/to/output/directory",
    "total_files": 3,
    "processed_files": 1
}
```

成功完成：
```json
{
    "task_id": "batch_1709123456_0",
    "status": "completed",
    "output_directory": "/path/to/output/directory",
    "total_files": 3,
    "processed_files": 3,
    "process_time": 15.67
}
```

部分失败：
```json
{
    "task_id": "batch_1709123456_0",
    "status": "completed",
    "output_directory": "/path/to/output/directory",
    "total_files": 3,
    "processed_files": 2,
    "process_time": 10.45,
    "errors": [
        {
            "filename": "file3.wav",
            "error": "文本过长无法处理"
        }
    ]
}
```

### 6. 健康检查

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
   - 使用 `/api/tts/tasks` 创建单个语音生成任务，或使用 `/api/tts/batch_tasks` 创建批量语音生成任务
   - 定期通过 `/api/tts/tasks/{task_id}` 查询任务状态
   - 当状态为 "completed" 时，从输出目录获取生成的音频文件

2. 注意事项：
   - 建议对任务状态查询设置合理的轮询间隔（建议3-5秒）
   - 输出目录需要确保具有写入权限
   - 参考音频文件名需要使用 `/api/tts/prompts` 接口返回的值
   - 任务状态信息会在服务重启后丢失，请及时保存任务ID和状态
   - 批量任务会按顺序处理文件，不会并发处理，以确保音色一致性
   - 批量任务中即使某些文件处理失败，也会继续处理其他文件
