"""统一工作空间核心组件

实现任务文件系统管理器，支持任务目录创建和文件命名规范，
文件引用模型和元数据管理，以及任务状态持久化机制。
"""

import os
import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from ..models.types import AgentType, TaskType
from ..models.workspace import FileType, TaskStatus, FileReference, TaskMetadata
from ..models.workspace import FileType, TaskStatus


from ..models.workspace import FileReference, TaskMetadata


class FileNamingManager:
    """文件命名管理器

    实现文件命名规范：[步骤编号]_[Agent名称]_[任务类型]_[版本号].后缀
    """

    @staticmethod
    def generate_filename(
        step_number: int,
        agent_type: AgentType,
        task_type: str,
        version: int = 1,
        file_type: FileType = FileType.MARKDOWN,
    ) -> str:
        """生成标准文件名"""
        step_str = f"{step_number:02d}"
        agent_name = agent_type.value.capitalize()
        return f"{step_str}_{agent_name}_{task_type}_v{version}.{file_type.value}"

    @staticmethod
    def parse_filename(filename: str) -> Dict[str, Any]:
        """解析文件名获取信息"""
        try:
            name_part, ext = filename.rsplit(".", 1)
            parts = name_part.split("_")

            if len(parts) < 4:
                return {}

            step_number = int(parts[0])
            agent_name = parts[1].lower()
            task_type = parts[2]
            version_str = parts[3]
            version = int(version_str[1:]) if version_str.startswith("v") else 1

            return {
                "step_number": step_number,
                "agent_type": agent_name,
                "task_type": task_type,
                "version": version,
                "file_type": FileType(ext),
            }
        except (ValueError, IndexError):
            return {}

    @staticmethod
    def get_next_version(workspace_path: str, base_filename: str) -> int:
        """获取下一个版本号"""
        workspace = Path(workspace_path)
        if not workspace.exists():
            return 1

        # 解析基础文件名
        name_part, ext = base_filename.rsplit(".", 1)
        base_parts = name_part.split("_")
        if len(base_parts) < 3:
            return 1

        base_pattern = "_".join(base_parts[:3])
        max_version = 0

        for file_path in workspace.iterdir():
            if file_path.is_file():
                filename = file_path.name
                if filename.startswith(base_pattern):
                    parsed = FileNamingManager.parse_filename(filename)
                    if parsed and parsed.get("version", 0) > max_version:
                        max_version = parsed["version"]

        return max_version + 1


class TaskFileSystemManager:
    """任务文件系统管理器"""

    def __init__(self, base_workspace_path: str = "data/tasks"):
        self.base_workspace_path = Path(base_workspace_path)
        self.base_workspace_path.mkdir(parents=True, exist_ok=True)
        self.naming_manager = FileNamingManager()

    def create_task_workspace(
        self,
        title: str,
        description: str,
        task_type: TaskType,
        task_id: Optional[str] = None,
    ) -> TaskMetadata:
        """创建任务工作空间"""
        if task_id is None:
            task_id = str(uuid.uuid4())

        workspace_path = self.base_workspace_path / task_id
        workspace_path.mkdir(parents=True, exist_ok=True)

        # 创建任务元数据
        now = datetime.now()
        metadata = TaskMetadata(
            task_id=task_id,
            title=title,
            description=description,
            task_type=task_type,
            status=TaskStatus.CREATED,
            created_at=now,
            updated_at=now,
            workspace_path=str(workspace_path),
            files=[],
            current_step=0,
            total_steps=0,
            active_agent=None,
            error_count=0,
        )

        # 保存元数据
        self._save_task_metadata(metadata)

        # 创建初始文件
        self._create_initial_files(workspace_path, task_id)

        return metadata

    def _create_initial_files(self, workspace_path: Path, task_id: str):
        """创建初始文件"""
        # 创建 todo.md 文件
        todo_content = f"""# 任务待办清单

任务ID: {task_id}
创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 当前状态
- [ ] 任务初始化完成

## 待执行步骤
（将由智能体动态更新）

## 注意事项
此文件将被智能体动态更新，用于引导模型注意力聚焦任务目标。
"""
        todo_path = workspace_path / "todo.md"
        todo_path.write_text(todo_content, encoding="utf-8")

        # 创建 _error.log 文件
        error_log_path = workspace_path / "_error.log"
        error_log_path.write_text("", encoding="utf-8")

    def _save_task_metadata(self, metadata: TaskMetadata):
        """保存任务元数据"""
        metadata_path = Path(metadata.workspace_path) / "task_metadata.json"

        # 自定义序列化处理枚举和日期时间
        def custom_serializer(obj):
            if isinstance(obj, (TaskType, TaskStatus, FileType)):
                return obj.value
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(
                metadata.dict(),
                f,
                ensure_ascii=False,
                indent=2,
                default=custom_serializer,
            )

    def load_task_metadata(self, task_id: str) -> Optional[TaskMetadata]:
        """加载任务元数据"""
        workspace_path = self.base_workspace_path / task_id
        metadata_path = workspace_path / "task_metadata.json"

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 转换枚举字符串回枚举对象
            if "task_type" in data:
                data["task_type"] = TaskType.from_string(data["task_type"])
            if "status" in data:
                data["status"] = TaskStatus(data["status"])

            # 转换日期时间字符串
            if "created_at" in data:
                data["created_at"] = datetime.fromisoformat(data["created_at"])
            if "updated_at" in data:
                data["updated_at"] = datetime.fromisoformat(data["updated_at"])

            # 转换文件引用
            if "files" in data:
                files = []
                for file_data in data["files"]:
                    if "type" in file_data:
                        file_data["type"] = FileType(file_data["type"])
                    if "created_at" in file_data:
                        file_data["created_at"] = datetime.fromisoformat(
                            file_data["created_at"]
                        )
                    if "updated_at" in file_data:
                        file_data["updated_at"] = datetime.fromisoformat(
                            file_data["updated_at"]
                        )
                    files.append(FileReference(**file_data))
                data["files"] = files

            return TaskMetadata(**data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error loading task metadata: {e}")
            return None

    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """更新任务状态"""
        metadata = self.load_task_metadata(task_id)
        if not metadata:
            return False

        metadata.status = status
        metadata.updated_at = datetime.now()
        self._save_task_metadata(metadata)
        return True

    def add_file_reference(
        self,
        task_id: str,
        file_path: str,
        created_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[FileReference]:
        """添加文件引用"""
        task_metadata = self.load_task_metadata(task_id)
        if not task_metadata:
            return None

        full_path = Path(task_metadata.workspace_path) / file_path
        if not full_path.exists():
            return None

        # 计算文件校验和
        checksum = self._calculate_checksum(full_path)

        # 确定文件类型
        file_type = FileType.TEXT
        if full_path.suffix:
            try:
                file_type = FileType(full_path.suffix[1:])
            except ValueError:
                pass

        # 创建文件引用
        now = datetime.now()
        file_ref = FileReference(
            path=file_path,
            type=file_type,
            size=full_path.stat().st_size,
            checksum=checksum,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        # 更新任务元数据
        task_metadata.files.append(file_ref)
        task_metadata.updated_at = now
        self._save_task_metadata(task_metadata)

        return file_ref

    def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件校验和"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def create_agent_file(
        self,
        task_id: str,
        step_number: int,
        agent_type: AgentType,
        task_type: str,
        content: str,
        file_type: FileType = FileType.MARKDOWN,
    ) -> Optional[str]:
        """创建智能体输出文件"""
        task_metadata = self.load_task_metadata(task_id)
        if not task_metadata:
            return None

        workspace_path = Path(task_metadata.workspace_path)

        # 生成文件名
        base_filename = self.naming_manager.generate_filename(
            step_number, agent_type, task_type, 1, file_type
        )

        # 获取下一个版本号
        version = self.naming_manager.get_next_version(
            str(workspace_path), base_filename
        )
        filename = self.naming_manager.generate_filename(
            step_number, agent_type, task_type, version, file_type
        )

        # 写入文件
        file_path = workspace_path / filename
        file_path.write_text(content, encoding="utf-8")

        # 添加文件引用
        self.add_file_reference(
            task_id,
            filename,
            agent_type.value,
            {"step_number": step_number, "task_type": task_type, "version": version},
        )

        return filename

    def update_todo_file(self, task_id: str, content: str) -> bool:
        """更新todo.md文件"""
        task_metadata = self.load_task_metadata(task_id)
        if not task_metadata:
            return False

        todo_path = Path(task_metadata.workspace_path) / "todo.md"
        todo_path.write_text(content, encoding="utf-8")

        # 更新任务元数据时间戳
        task_metadata.updated_at = datetime.now()
        self._save_task_metadata(task_metadata)

        return True

    def append_error_log(self, task_id: str, error_message: str) -> bool:
        """追加错误日志"""
        task_metadata = self.load_task_metadata(task_id)
        if not task_metadata:
            return False

        error_log_path = Path(task_metadata.workspace_path) / "_error.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {error_message}\n"

        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)

        # 更新错误计数
        task_metadata.error_count += 1
        task_metadata.updated_at = datetime.now()
        self._save_task_metadata(task_metadata)

        return True

    def get_task_files(self, task_id: str) -> List[FileReference]:
        """获取任务所有文件"""
        task_metadata = self.load_task_metadata(task_id)
        if not task_metadata:
            return []
        return task_metadata.files

    def get_latest_file_by_agent(
        self, task_id: str, agent_type: AgentType
    ) -> Optional[FileReference]:
        """获取指定智能体的最新文件"""
        files = self.get_task_files(task_id)
        agent_files = [f for f in files if f.created_by == agent_type.value]

        if not agent_files:
            return None

        return max(agent_files, key=lambda f: f.updated_at)

    def list_tasks(self) -> List[TaskMetadata]:
        """列出所有任务"""
        tasks = []
        for task_dir in self.base_workspace_path.iterdir():
            if task_dir.is_dir():
                metadata = self.load_task_metadata(task_dir.name)
                if metadata:
                    tasks.append(metadata)

        return sorted(tasks, key=lambda t: t.updated_at, reverse=True)

    def delete_task(self, task_id: str) -> bool:
        """删除任务工作空间"""
        workspace_path = self.base_workspace_path / task_id
        if not workspace_path.exists():
            return False

        import shutil

        shutil.rmtree(workspace_path)
        return True

    def get_task_recovery_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务恢复信息"""
        task_metadata = self.load_task_metadata(task_id)
        if not task_metadata:
            return None

        workspace_path = Path(task_metadata.workspace_path)

        # 获取最新文件
        latest_files = {}
        for file_ref in task_metadata.files:
            agent = file_ref.created_by
            if (
                agent not in latest_files
                or file_ref.updated_at > latest_files[agent].updated_at
            ):
                latest_files[agent] = file_ref

        # 读取todo.md内容
        todo_path = workspace_path / "todo.md"
        todo_content = ""
        if todo_path.exists():
            todo_content = todo_path.read_text(encoding="utf-8")

        # 读取错误日志
        error_log_path = workspace_path / "_error.log"
        error_log = ""
        if error_log_path.exists():
            error_log = error_log_path.read_text(encoding="utf-8")

        return {
            "task_metadata": task_metadata,
            "latest_files": latest_files,
            "todo_content": todo_content,
            "error_log": error_log,
            "can_resume": task_metadata.status
            in [TaskStatus.IN_PROGRESS, TaskStatus.PAUSED],
        }


# 全局工作空间管理器实例
workspace_manager = TaskFileSystemManager()
