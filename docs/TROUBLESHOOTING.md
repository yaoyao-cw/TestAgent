# TestAgent 故障排除和维护手册

## 概述

本手册提供TestAgent系统常见问题的诊断方法、解决方案和预防措施，帮助运维人员快速定位和解决系统故障，确保系统稳定运行。

## 智能错误诊断

### 1. 错误消息格式化

TestAgent提供智能错误诊断功能，自动将技术错误转换为用户友好的格式：

```bash
#!/bin/bash
# scripts/format_error.sh

ERROR_MESSAGE="$1"
ERROR_TYPE="$2"
CONTEXT="$3"

# 调用错误格式化API
curl -X POST "http://localhost:8000/api/v1/errors/format" \
     -H "Content-Type: application/json" \
     -d "{
       \"error_type\": \"${ERROR_TYPE:-generic_error}\",
       \"error_message\": \"$ERROR_MESSAGE\",
       \"context\": ${CONTEXT:-{}},
       \"style\": \"technical\"
     }" | jq '.formatted_message'
```

**使用示例**:
```bash
# 格式化网络错误
./scripts/format_error.sh "Connection timeout" "network_error" '{"service": "API服务", "url": "https://api.example.com"}'

# 格式化API错误
./scripts/format_error.sh "HTTP 500 Internal Server Error" "api_error" '{"status_code": 500, "endpoint": "/api/v1/tasks"}'
```

### 2. 自动解决方案建议

系统能够基于错误类型和上下文自动生成解决方案建议：

```python
#!/usr/bin/env python3
# scripts/get_error_suggestions.py

import requests
import json
import sys

def get_error_suggestions(error_message, error_type="generic_error", context=None):
    """获取错误解决建议"""
    
    payload = {
        "error_type": error_type,
        "error_message": error_message,
        "context": context or {},
        "style": "technical"
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/errors/format",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        formatted_msg = result.get("formatted_message", {})
        
        print(f"错误类型: {formatted_msg.get('error_type', 'unknown')}")
        print(f"严重程度: {formatted_msg.get('severity', 'unknown')}")
        print(f"错误描述: {formatted_msg.get('message', error_message)}")
        
        suggestions = formatted_msg.get('suggestions', [])
        if suggestions:
            print("\n建议解决方案:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"  {i}. {suggestion}")
        
        action_buttons = formatted_msg.get('action_buttons', [])
        if action_buttons:
            print("\n可执行操作:")
            for button in action_buttons:
                print(f"  - {button.get('text', '')}: {button.get('action', '')}")
        
        if formatted_msg.get('help_url'):
            print(f"\n帮助文档: {formatted_msg.get('help_url')}")
        
        if formatted_msg.get('error_id'):
            print(f"错误ID: {formatted_msg.get('error_id')}")
            
    except requests.RequestException as e:
        print(f"获取建议失败: {e}")
        print("请检查系统状态或联系技术支持")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python get_error_suggestions.py <错误消息> [错误类型] [上下文JSON]")
        sys.exit(1)
    
    error_msg = sys.argv[1]
    error_type = sys.argv[2] if len(sys.argv) > 2 else "generic_error"
    context = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    
    get_error_suggestions(error_msg, error_type, context)
```

## 快速诊断工具

### 3. 系统健康检查

#### 1.1 一键健康检查脚本
```bash
#!/bin/bash
# scripts/healthcheck.sh

echo "=== TestAgent 系统健康检查 ==="

# 检查服务状态
echo "1. 检查服务状态..."
docker-compose ps

# 检查API健康
echo "2. 检查API健康..."
curl -s http://localhost:8000/api/v1/monitoring/health | jq .

# 检查数据库连接
echo "3. 检查数据库连接..."
curl -s http://localhost:8000/api/v1/monitoring/database | jq .

# 检查缓存状态
echo "4. 检查缓存状态..."
redis-cli -h localhost -p 6379 ping

# 检查磁盘空间
echo "5. 检查磁盘空间..."
df -h | grep -E "(/$|/data|/logs)"

# 检查内存使用
echo "6. 检查内存使用..."
free -h

# 检查最近错误日志
echo "7. 检查最近错误日志..."
docker-compose logs --tail=50 testagent | grep -i error

echo "=== 健康检查完成 ==="
```

#### 1.2 监控模式脚本
```bash
#!/bin/bash
# scripts/monitor.sh

echo "启动监控模式..."

while true; do
    clear
    echo "=== TestAgent 实时监控 $(date) ==="
    
    # 系统负载
    echo "系统负载:"
    uptime
    
    # 容器状态
    echo -e "\n容器状态:"
    docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    
    # 活跃任务数
    echo -e "\n活跃任务数:"
    curl -s http://localhost:8000/api/v1/monitoring/metrics | jq '.active_tasks'
    
    # 错误率
    echo -e "\n错误率:"
    curl -s http://localhost:8000/api/v1/monitoring/metrics | jq '.error_rate'
    
    # 缓存命中率
    echo -e "\n缓存命中率:"
    curl -s http://localhost:8000/api/v1/monitoring/metrics | jq '.cache_hit_rate'
    
    sleep 5
done
```

### 4. 日志分析工具

#### 2.1 日志聚合脚本
```bash
#!/bin/bash
# scripts/analyze_logs.sh

LOG_LEVEL=${1:-ERROR}
TIME_RANGE=${2:-1h}

echo "分析最近 $TIME_RANGE 的 $LOG_LEVEL 级别日志..."

# 聚合所有服务日志
docker-compose logs --since=$TIME_RANGE testagent | \
grep -i $LOG_LEVEL | \
awk '{
    # 提取时间戳和错误信息
    timestamp = $1 " " $2
    message = substr($0, index($0, $3))
    
    # 统计错误类型
    if (match(message, /[A-Za-z]+Error/)) {
        error_type = substr(message, RSTART, RLENGTH)
        error_count[error_type]++
    }
    
    # 记录详细信息
    logs[NR] = timestamp ": " message
}
END {
    print "=== 错误统计 ==="
    for (error in error_count) {
        print error ": " error_count[error]
    }
    
    print "\n=== 详细日志 ==="
    for (i = 1; i <= NR && i <= 20; i++) {
        print logs[i]
    }
}'
```

#### 2.2 性能分析脚本
```python
#!/usr/bin/env python3
# scripts/performance_analyzer.py

import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_performance_logs(log_file, hours=1):
    """分析性能日志"""
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    response_times = defaultdict(list)
    error_counts = defaultdict(int)
    agent_performance = defaultdict(list)
    
    with open(log_file, 'r') as f:
        for line in f:
            try:
                log_entry = json.loads(line)
                log_time = datetime.fromisoformat(log_entry['timestamp'])
                
                if log_time < cutoff_time:
                    continue
                
                # 分析响应时间
                if log_entry.get('type') == 'performance':
                    metric_name = log_entry.get('metric_name')
                    value = log_entry.get('value')
                    
                    if metric_name == 'response_time':
                        endpoint = log_entry.get('labels', {}).get('endpoint', 'unknown')
                        response_times[endpoint].append(value)
                    
                    elif metric_name == 'agent_execution_time':
                        agent_name = log_entry.get('labels', {}).get('agent_name', 'unknown')
                        agent_performance[agent_name].append(value)
                
                # 统计错误
                elif log_entry.get('level') == 'ERROR':
                    error_type = log_entry.get('error_type', 'unknown')
                    error_counts[error_type] += 1
                    
            except (json.JSONDecodeError, KeyError):
                continue
    
    # 生成报告
    print("=== 性能分析报告 ===")
    print(f"分析时间范围: 最近 {hours} 小时")
    
    print("\n1. API响应时间统计:")
    for endpoint, times in response_times.items():
        if times:
            avg_time = sum(times) / len(times)
            max_time = max(times)
            print(f"  {endpoint}: 平均 {avg_time:.2f}s, 最大 {max_time:.2f}s, 请求数 {len(times)}")
    
    print("\n2. 智能体执行时间统计:")
    for agent, times in agent_performance.items():
        if times:
            avg_time = sum(times) / len(times)
            max_time = max(times)
            print(f"  {agent}: 平均 {avg_time:.2f}s, 最大 {max_time:.2f}s, 执行次数 {len(times)}")
    
    print("\n3. 错误统计:")
    for error_type, count in error_counts.items():
        print(f"  {error_type}: {count} 次")

if __name__ == "__main__":
    log_file = sys.argv[1] if len(sys.argv) > 1 else "logs/testagent.log"
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    analyze_performance_logs(log_file, hours)
```

## 常见问题诊断

### 1. 服务启动问题

#### 1.1 容器启动失败

**症状**: Docker容器无法启动或立即退出

**诊断步骤**:
```bash
# 1. 查看容器状态
docker-compose ps

# 2. 查看启动日志
docker-compose logs testagent

# 3. 检查配置文件
docker-compose config

# 4. 检查端口占用
netstat -tulpn | grep :8000
```

**常见原因和解决方案**:

**端口冲突**:
```bash
# 查找占用端口的进程
lsof -i :8000

# 停止占用进程或修改配置端口
# 修改 docker-compose.yml 中的端口映射
ports:
  - "8001:8000"  # 改为8001端口
```

**配置文件错误**:
```bash
# 检查环境变量文件
cat .env | grep -v '^#' | grep -v '^$'

# 验证配置文件语法
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

**依赖服务未就绪**:
```yaml
# 在 docker-compose.yml 中添加健康检查
services:
  testagent:
    depends_on:
      redis:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    
  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### 1.2 Python依赖问题

**症状**: 导入模块失败或版本冲突

**诊断步骤**:
```bash
# 1. 检查Python版本
python --version

# 2. 检查已安装包
pip list

# 3. 验证关键依赖
python -c "import fastapi, langchain, chromadb"

# 4. 检查虚拟环境
which python
echo $VIRTUAL_ENV
```

**解决方案**:
```bash
# 重新创建虚拟环境
rm -rf venv
python -m venv venv
source venv/bin/activate

# 升级pip和安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 如果有版本冲突，使用具体版本
pip install fastapi==0.104.1
```

### 2. API响应问题

#### 2.1 API响应慢

**症状**: API请求响应时间超过预期

**诊断步骤**:
```bash
# 1. 测试API响应时间
time curl -X GET "http://localhost:8000/api/v1/monitoring/health"

# 2. 检查系统负载
top
htop

# 3. 检查数据库连接
curl "http://localhost:8000/api/v1/monitoring/database"

# 4. 检查缓存状态
redis-cli info stats
```

**性能分析**:
```python
# scripts/api_benchmark.py
import time
import requests
import statistics

def benchmark_api(url, num_requests=10):
    """API性能基准测试"""
    response_times = []
    
    for i in range(num_requests):
        start_time = time.time()
        try:
            response = requests.get(url, timeout=30)
            end_time = time.time()
            
            response_time = end_time - start_time
            response_times.append(response_time)
            
            print(f"请求 {i+1}: {response_time:.3f}s, 状态码: {response.status_code}")
            
        except requests.RequestException as e:
            print(f"请求 {i+1} 失败: {e}")
    
    if response_times:
        print(f"\n统计结果:")
        print(f"平均响应时间: {statistics.mean(response_times):.3f}s")
        print(f"最小响应时间: {min(response_times):.3f}s")
        print(f"最大响应时间: {max(response_times):.3f}s")
        print(f"标准差: {statistics.stdev(response_times):.3f}s")

if __name__ == "__main__":
    benchmark_api("http://localhost:8000/api/v1/monitoring/health")
```

**优化方案**:

**启用缓存**:
```python
# 检查缓存配置
curl "http://localhost:8000/api/v1/monitoring/cache"

# 清理过期缓存
redis-cli FLUSHDB
```

**数据库优化**:
```bash
# 检查ChromaDB状态
curl "http://localhost:8001/api/v1/heartbeat"

# 重建索引（如果需要）
curl -X POST "http://localhost:8001/api/v1/collections/rebuild_index"
```

#### 2.2 API返回错误

**症状**: API返回4xx或5xx错误

**诊断步骤**:
```bash
# 1. 查看详细错误信息
curl -v "http://localhost:8000/api/v1/tasks/submit" \
     -H "Content-Type: application/json" \
     -d '{"invalid": "data"}'

# 2. 检查API文档
curl "http://localhost:8000/docs"

# 3. 查看应用日志
docker-compose logs --tail=100 testagent | grep ERROR
```

**常见错误处理**:

**422 验证错误**:
```bash
# 检查请求格式
curl -X POST "http://localhost:8000/api/v1/tasks/submit" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "测试任务",
       "description": "任务描述",
       "task_type": "functional_testing"
     }'
```

**500 内部服务器错误**:
```bash
# 查看详细错误堆栈
docker-compose logs testagent | grep -A 20 "Internal Server Error"

# 检查依赖服务状态
curl "http://localhost:6379"  # Redis
curl "http://localhost:8001/api/v1/heartbeat"  # ChromaDB
```

### 3. 智能体执行问题

#### 3.1 智能体无响应

**症状**: 任务提交后智能体长时间无响应

**诊断步骤**:
```bash
# 1. 检查任务状态
curl "http://localhost:8000/api/v1/tasks/{task_id}/status"

# 2. 查看任务工作目录
ls -la data/tasks/{task_id}/

# 3. 检查智能体日志
docker-compose logs testagent | grep "agent_execution"

# 4. 检查LLM服务状态
curl "http://localhost:8000/api/v1/monitoring/llm"
```

**问题排查**:

**LLM服务问题**:
```python
# scripts/test_llm.py
import os
from openai import OpenAI

def test_llm_connection():
    """测试LLM连接"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print("LLM连接正常")
        print(f"响应: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"LLM连接失败: {e}")

if __name__ == "__main__":
    test_llm_connection()
```

**任务死锁检测**:
```python
# scripts/detect_deadlock.py
import json
import os
from datetime import datetime, timedelta

def detect_task_deadlock(tasks_dir="data/tasks"):
    """检测任务死锁"""
    
    current_time = datetime.now()
    deadlock_threshold = timedelta(hours=1)  # 1小时无更新视为死锁
    
    for task_id in os.listdir(tasks_dir):
        task_path = os.path.join(tasks_dir, task_id)
        if not os.path.isdir(task_path):
            continue
        
        # 检查最后更新时间
        files = [f for f in os.listdir(task_path) if f.endswith(('.md', '.json', '.py'))]
        if not files:
            continue
        
        latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(task_path, f)))
        latest_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(task_path, latest_file)))
        
        if current_time - latest_time > deadlock_threshold:
            print(f"可能的死锁任务: {task_id}")
            print(f"  最后更新: {latest_time}")
            print(f"  最后文件: {latest_file}")
            
            # 检查错误日志
            error_log = os.path.join(task_path, "_error.log")
            if os.path.exists(error_log):
                with open(error_log, 'r') as f:
                    errors = f.readlines()
                    if errors:
                        print(f"  最近错误: {errors[-1].strip()}")

if __name__ == "__main__":
    detect_task_deadlock()
```

#### 3.2 智能体执行错误

**症状**: 智能体执行过程中出现错误

**诊断步骤**:
```bash
# 1. 查看任务错误日志
cat data/tasks/{task_id}/_error.log

# 2. 检查智能体输出文件
ls -la data/tasks/{task_id}/

# 3. 分析错误模式
grep -r "Error" data/tasks/{task_id}/
```

**错误分类处理**:

**工具调用错误**:
```bash
# 检查工具状态
curl "http://localhost:8000/api/v1/monitoring/tools"

# 测试沙箱环境
curl -X POST "http://localhost:8000/api/v1/tools/sandbox/test" \
     -H "Content-Type: application/json" \
     -d '{"code": "print(\"Hello World\")"}'
```

**知识库检索错误**:
```bash
# 检查ChromaDB状态
curl "http://localhost:8001/api/v1/heartbeat"

# 测试检索功能
curl -X POST "http://localhost:8000/api/v1/knowledge/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "test query", "top_k": 5}'
```

### 4. 性能问题

#### 4.1 内存使用过高

**症状**: 系统内存使用率持续升高

**诊断步骤**:
```bash
# 1. 检查内存使用
free -h
ps aux --sort=-%mem | head -10

# 2. 检查容器内存使用
docker stats

# 3. 分析内存泄漏
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB')
"
```

**内存优化**:

**清理缓存**:
```bash
# 清理Redis缓存
redis-cli FLUSHALL

# 清理Python缓存
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
```

**调整缓存配置**:
```yaml
# config/config.yaml
cache:
  redis:
    max_memory: "512MB"
    eviction_policy: "allkeys-lru"
  
  application:
    max_context_length: 4000
    cache_cleanup_interval: 300  # 5分钟
```

**内存监控脚本**:
```python
# scripts/memory_monitor.py
import psutil
import time
import json
from datetime import datetime

def monitor_memory(duration=3600, interval=60):
    """监控内存使用情况"""
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        # 系统内存
        memory = psutil.virtual_memory()
        
        # 进程内存
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                if proc.info['memory_percent'] > 1.0:  # 只记录占用超过1%的进程
                    processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 记录数据
        data = {
            'timestamp': datetime.now().isoformat(),
            'system_memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used
            },
            'top_processes': sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:10]
        }
        
        print(json.dumps(data, indent=2))
        time.sleep(interval)

if __name__ == "__main__":
    monitor_memory()
```

#### 4.2 磁盘空间不足

**症状**: 磁盘使用率接近100%

**诊断步骤**:
```bash
# 1. 检查磁盘使用情况
df -h

# 2. 查找大文件
du -h --max-depth=1 | sort -hr

# 3. 检查日志文件大小
du -h logs/

# 4. 检查任务数据大小
du -h data/tasks/
```

**清理策略**:

**日志清理**:
```bash
# 清理旧日志文件
find logs/ -name "*.log" -mtime +7 -delete

# 配置日志轮转
# /etc/logrotate.d/testagent
/app/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 testagent testagent
}
```

**任务数据清理**:
```python
# scripts/cleanup_tasks.py
import os
import shutil
from datetime import datetime, timedelta

def cleanup_old_tasks(tasks_dir="data/tasks", days=30):
    """清理旧任务数据"""
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    for task_id in os.listdir(tasks_dir):
        task_path = os.path.join(tasks_dir, task_id)
        if not os.path.isdir(task_path):
            continue
        
        # 检查任务创建时间
        create_time = datetime.fromtimestamp(os.path.getctime(task_path))
        
        if create_time < cutoff_date:
            print(f"删除旧任务: {task_id} (创建于 {create_time})")
            shutil.rmtree(task_path)

if __name__ == "__main__":
    cleanup_old_tasks()
```

**磁盘监控**:
```bash
# scripts/disk_monitor.sh
#!/bin/bash

THRESHOLD=80  # 磁盘使用率阈值

while true; do
    USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ $USAGE -gt $THRESHOLD ]; then
        echo "警告: 磁盘使用率 ${USAGE}% 超过阈值 ${THRESHOLD}%"
        
        # 自动清理
        find logs/ -name "*.log" -mtime +3 -delete
        docker system prune -f
        
        # 发送告警（可选）
        # curl -X POST "http://alert-manager/api/v1/alerts" ...
    fi
    
    sleep 300  # 5分钟检查一次
done
```

## 维护操作

### 1. 定期维护任务

#### 1.1 每日维护清单

**自动化脚本**:
```bash
#!/bin/bash
# scripts/daily_maintenance.sh

echo "=== 每日维护任务开始 $(date) ==="

# 1. 健康检查
echo "1. 执行健康检查..."
./scripts/healthcheck.sh

# 2. 清理临时文件
echo "2. 清理临时文件..."
find /tmp -name "testagent_*" -mtime +1 -delete

# 3. 日志轮转
echo "3. 执行日志轮转..."
logrotate /etc/logrotate.d/testagent

# 4. 缓存优化
echo "4. 优化缓存..."
redis-cli MEMORY PURGE

# 5. 数据库维护
echo "5. 数据库维护..."
curl -X POST "http://localhost:8001/api/v1/collections/optimize"

# 6. 性能报告
echo "6. 生成性能报告..."
python scripts/performance_analyzer.py logs/testagent.log 24

echo "=== 每日维护任务完成 $(date) ==="
```

#### 1.2 每周维护清单

**维护脚本**:
```bash
#!/bin/bash
# scripts/weekly_maintenance.sh

echo "=== 每周维护任务开始 $(date) ==="

# 1. 系统更新检查
echo "1. 检查系统更新..."
apt list --upgradable

# 2. 清理旧任务数据
echo "2. 清理旧任务数据..."
python scripts/cleanup_tasks.py

# 3. 数据库备份
echo "3. 执行数据库备份..."
./scripts/backup_database.sh

# 4. 性能基准测试
echo "4. 执行性能基准测试..."
python scripts/api_benchmark.py

# 5. 安全扫描
echo "5. 执行安全扫描..."
./scripts/security_scan.sh

# 6. 生成周报
echo "6. 生成维护周报..."
python scripts/generate_weekly_report.py

echo "=== 每周维护任务完成 $(date) ==="
```

### 2. 备份和恢复

#### 2.1 数据备份策略

**备份脚本**:
```bash
#!/bin/bash
# scripts/backup_database.sh

BACKUP_DIR="/backup/testagent"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "开始备份数据库..."

# 1. 备份Redis数据
echo "备份Redis数据..."
redis-cli --rdb $BACKUP_DIR/redis_$DATE.rdb

# 2. 备份ChromaDB数据
echo "备份ChromaDB数据..."
tar -czf $BACKUP_DIR/chromadb_$DATE.tar.gz data/vectordb/

# 3. 备份任务数据
echo "备份任务数据..."
tar -czf $BACKUP_DIR/tasks_$DATE.tar.gz data/tasks/

# 4. 备份配置文件
echo "备份配置文件..."
tar -czf $BACKUP_DIR/config_$DATE.tar.gz config/ .env

# 5. 清理旧备份（保留30天）
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete

echo "备份完成: $BACKUP_DIR"
```

#### 2.2 数据恢复流程

**恢复脚本**:
```bash
#!/bin/bash
# scripts/restore_database.sh

BACKUP_DIR="/backup/testagent"
RESTORE_DATE=$1

if [ -z "$RESTORE_DATE" ]; then
    echo "用法: $0 <备份日期> (格式: YYYYMMDD_HHMMSS)"
    echo "可用备份:"
    ls -la $BACKUP_DIR/ | grep tar.gz
    exit 1
fi

echo "开始恢复数据 (备份日期: $RESTORE_DATE)..."

# 1. 停止服务
echo "停止服务..."
docker-compose down

# 2. 恢复Redis数据
echo "恢复Redis数据..."
if [ -f "$BACKUP_DIR/redis_$RESTORE_DATE.rdb" ]; then
    cp $BACKUP_DIR/redis_$RESTORE_DATE.rdb data/redis/dump.rdb
fi

# 3. 恢复ChromaDB数据
echo "恢复ChromaDB数据..."
if [ -f "$BACKUP_DIR/chromadb_$RESTORE_DATE.tar.gz" ]; then
    rm -rf data/vectordb/
    tar -xzf $BACKUP_DIR/chromadb_$RESTORE_DATE.tar.gz
fi

# 4. 恢复任务数据
echo "恢复任务数据..."
if [ -f "$BACKUP_DIR/tasks_$RESTORE_DATE.tar.gz" ]; then
    rm -rf data/tasks/
    tar -xzf $BACKUP_DIR/tasks_$RESTORE_DATE.tar.gz
fi

# 5. 恢复配置文件
echo "恢复配置文件..."
if [ -f "$BACKUP_DIR/config_$RESTORE_DATE.tar.gz" ]; then
    tar -xzf $BACKUP_DIR/config_$RESTORE_DATE.tar.gz
fi

# 6. 重启服务
echo "重启服务..."
docker-compose up -d

# 7. 验证恢复
echo "验证恢复..."
sleep 30
./scripts/healthcheck.sh

echo "数据恢复完成"
```

### 3. 系统升级

#### 3.1 升级前检查

**升级检查脚本**:
```bash
#!/bin/bash
# scripts/pre_upgrade_check.sh

echo "=== 升级前检查 ==="

# 1. 检查当前版本
echo "1. 当前版本信息:"
curl -s http://localhost:8000/api/v1/monitoring/version

# 2. 检查系统状态
echo "2. 系统状态检查:"
./scripts/healthcheck.sh

# 3. 检查磁盘空间
echo "3. 磁盘空间检查:"
df -h

# 4. 检查运行中的任务
echo "4. 运行中的任务:"
curl -s http://localhost:8000/api/v1/tasks/active | jq '.count'

# 5. 创建升级前备份
echo "5. 创建升级前备份:"
./scripts/backup_database.sh

# 6. 检查配置兼容性
echo "6. 配置兼容性检查:"
python scripts/config_validator.py

echo "=== 升级前检查完成 ==="
```

#### 3.2 滚动升级流程

**升级脚本**:
```bash
#!/bin/bash
# scripts/rolling_upgrade.sh

NEW_VERSION=$1

if [ -z "$NEW_VERSION" ]; then
    echo "用法: $0 <新版本号>"
    exit 1
fi

echo "开始滚动升级到版本 $NEW_VERSION..."

# 1. 升级前检查
./scripts/pre_upgrade_check.sh

# 2. 拉取新镜像
echo "拉取新镜像..."
docker pull testagent:$NEW_VERSION

# 3. 更新配置
echo "更新配置..."
sed -i "s/testagent:.*/testagent:$NEW_VERSION/" docker-compose.yml

# 4. 滚动更新
echo "执行滚动更新..."
docker-compose up -d --no-deps testagent

# 5. 健康检查
echo "等待服务启动..."
sleep 30

for i in {1..10}; do
    if curl -s http://localhost:8000/api/v1/monitoring/health | grep -q "healthy"; then
        echo "服务启动成功"
        break
    fi
    
    if [ $i -eq 10 ]; then
        echo "服务启动失败，开始回滚..."
        ./scripts/rollback.sh
        exit 1
    fi
    
    sleep 10
done

# 6. 升级后验证
echo "升级后验证..."
./scripts/post_upgrade_check.sh

echo "升级完成"
```

#### 3.3 回滚流程

**回滚脚本**:
```bash
#!/bin/bash
# scripts/rollback.sh

BACKUP_DATE=$1

echo "开始回滚操作..."

# 1. 如果没有指定备份日期，使用最新备份
if [ -z "$BACKUP_DATE" ]; then
    BACKUP_DATE=$(ls -1 /backup/testagent/config_*.tar.gz | tail -1 | sed 's/.*config_\(.*\)\.tar\.gz/\1/')
    echo "使用最新备份: $BACKUP_DATE"
fi

# 2. 停止当前服务
echo "停止当前服务..."
docker-compose down

# 3. 恢复数据和配置
echo "恢复数据和配置..."
./scripts/restore_database.sh $BACKUP_DATE

# 4. 重启服务
echo "重启服务..."
docker-compose up -d

# 5. 验证回滚
echo "验证回滚..."
sleep 30
./scripts/healthcheck.sh

echo "回滚完成"
```

## 监控和告警

### 1. 监控指标

#### 1.1 关键指标定义

**业务指标**:
```python
BUSINESS_METRICS = {
    'task_completion_rate': {
        'description': '任务完成率',
        'threshold': {'warning': 0.8, 'critical': 0.6},
        'unit': 'percentage'
    },
    'average_task_duration': {
        'description': '平均任务执行时间',
        'threshold': {'warning': 600, 'critical': 1200},  # 秒
        'unit': 'seconds'
    },
    'agent_success_rate': {
        'description': '智能体成功率',
        'threshold': {'warning': 0.9, 'critical': 0.7},
        'unit': 'percentage'
    }
}
```

**系统指标**:
```python
SYSTEM_METRICS = {
    'cpu_usage': {
        'description': 'CPU使用率',
        'threshold': {'warning': 70, 'critical': 90},
        'unit': 'percentage'
    },
    'memory_usage': {
        'description': '内存使用率',
        'threshold': {'warning': 80, 'critical': 95},
        'unit': 'percentage'
    },
    'disk_usage': {
        'description': '磁盘使用率',
        'threshold': {'warning': 80, 'critical': 90},
        'unit': 'percentage'
    },
    'response_time': {
        'description': 'API响应时间',
        'threshold': {'warning': 5, 'critical': 10},
        'unit': 'seconds'
    }
}
```

#### 1.2 监控数据收集

**指标收集器**:
```python
# scripts/metrics_collector.py
import psutil
import requests
import json
import time
from datetime import datetime

class MetricsCollector:
    def __init__(self):
        self.api_base = "http://localhost:8000/api/v1"
    
    def collect_system_metrics(self):
        """收集系统指标"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_usage': psutil.cpu_percent(interval=1),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'load_average': psutil.getloadavg()[0]
        }
    
    def collect_business_metrics(self):
        """收集业务指标"""
        try:
            response = requests.get(f"{self.api_base}/monitoring/metrics")
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def collect_all_metrics(self):
        """收集所有指标"""
        metrics = {
            'system': self.collect_system_metrics(),
            'business': self.collect_business_metrics()
        }
        return metrics

def main():
    collector = MetricsCollector()
    
    while True:
        metrics = collector.collect_all_metrics()
        print(json.dumps(metrics, indent=2))
        
        # 发送到监控系统（如Prometheus）
        # send_to_prometheus(metrics)
        
        time.sleep(60)  # 每分钟收集一次

if __name__ == "__main__":
    main()
```

### 2. 告警配置

#### 2.1 告警规则

**Prometheus告警规则**:
```yaml
# monitoring/alert_rules.yml
groups:
  - name: testagent_alerts
    rules:
      - alert: HighErrorRate
        expr: testagent_error_rate > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "TestAgent错误率过高"
          description: "错误率 {{ $value }} 超过10%"
      
      - alert: TaskExecutionTimeout
        expr: testagent_task_duration > 1800
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "任务执行超时"
          description: "任务执行时间 {{ $value }}s 超过30分钟"
      
      - alert: ServiceDown
        expr: up{job="testagent"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "TestAgent服务下线"
          description: "TestAgent服务无法访问"
```

#### 2.2 告警通知

**告警处理脚本**:
```python
# scripts/alert_handler.py
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class AlertHandler:
    def __init__(self, config):
        self.config = config
    
    def send_email_alert(self, alert):
        """发送邮件告警"""
        msg = MIMEMultipart()
        msg['From'] = self.config['email']['from']
        msg['To'] = ', '.join(self.config['email']['to'])
        msg['Subject'] = f"[TestAgent Alert] {alert['summary']}"
        
        body = f"""
        告警详情:
        - 告警名称: {alert['alertname']}
        - 严重程度: {alert['severity']}
        - 描述: {alert['description']}
        - 时间: {alert['timestamp']}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(self.config['email']['smtp_server'])
        server.starttls()
        server.login(self.config['email']['username'], self.config['email']['password'])
        server.send_message(msg)
        server.quit()
    
    def send_webhook_alert(self, alert):
        """发送Webhook告警"""
        webhook_url = self.config['webhook']['url']
        
        payload = {
            'text': f"TestAgent告警: {alert['summary']}",
            'attachments': [{
                'color': 'danger' if alert['severity'] == 'critical' else 'warning',
                'fields': [
                    {'title': '告警名称', 'value': alert['alertname'], 'short': True},
                    {'title': '严重程度', 'value': alert['severity'], 'short': True},
                    {'title': '描述', 'value': alert['description'], 'short': False}
                ]
            }]
        }
        
        requests.post(webhook_url, json=payload)
    
    def handle_alert(self, alert):
        """处理告警"""
        if alert['severity'] == 'critical':
            self.send_email_alert(alert)
            self.send_webhook_alert(alert)
        elif alert['severity'] == 'warning':
            self.send_webhook_alert(alert)

# 配置示例
config = {
    'email': {
        'smtp_server': 'smtp.gmail.com:587',
        'from': 'alerts@company.com',
        'to': ['admin@company.com', 'ops@company.com'],
        'username': 'alerts@company.com',
        'password': 'password'
    },
    'webhook': {
        'url': 'https://hooks.slack.com/services/...'
    }
}
```

## 总结

本故障排除和维护手册提供了：

1. **快速诊断工具**: 帮助快速定位问题
2. **常见问题解决方案**: 涵盖启动、API、智能体、性能等问题
3. **维护操作指南**: 包括定期维护、备份恢复、系统升级
4. **监控告警配置**: 确保系统稳定运行

建议运维人员：
- 定期执行维护脚本
- 监控关键指标变化
- 及时响应告警信息
- 保持备份数据完整性
- 持续优化系统性能

通过遵循本手册的指导，可以确保TestAgent系统的稳定运行和高效维护。