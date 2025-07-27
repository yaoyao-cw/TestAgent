"""工作空间核心组件测试"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.core.workspace import TaskFileSystemManager, FileNamingManager
from src.models.types import TaskType, AgentType
from src.models.workspace import TaskStatus, FileType


class TestFileNamingManager:
    """文件命名管理器测试"""

    def test_generate_filename(self):
        """测试文件名生成"""
        filename = FileNamingManager.generate_filename(
            step_number=1,
            agent_type=AgentType.COORDINATOR,
            task_type="Init",
            version=1,
            file_type=FileType.MARKDOWN,
        )
        assert filename == "01_Coordinator_Init_v1.md"

    def test_parse_filename(self):
        """测试文件名解析"""
        filename = "02_Planner_Plan_v2.json"
        parsed = FileNamingManager.parse_filename(filename)

        assert parsed["step_number"] == 2
        assert parsed["agent_type"] == "planner"
        assert parsed["task_type"] == "Plan"
        assert parsed["version"] == 2
        assert parsed["file_type"] == FileType.JSON

    def test_parse_invalid_filename(self):
        """测试无效文件名解析"""
        filename = "invalid_filename.txt"
        parsed = FileNamingManager.parse_filename(filename)
        assert parsed == {}


class TestTaskFileSystemManager:
    """任务文件系统管理器测试"""

    @pytest.fixture
    def temp_workspace(self):
        """临时工作空间"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def manager(self, temp_workspace):
        """文件系统管理器实例"""
        return TaskFileSystemManager(temp_workspace)

    def test_create_task_workspace(self, manager):
        """测试创建任务工作空间"""
        metadata = manager.create_task_workspace(
            title="测试任务",
            description="这是一个测试任务",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        assert metadata.title == "测试任务"
        assert metadata.description == "这是一个测试任务"
        assert metadata.task_type == TaskType.TEST_CASE_GENERATION
        assert metadata.status == TaskStatus.CREATED
        assert len(metadata.task_id) > 0

        # 检查工作空间目录是否创建
        workspace_path = Path(metadata.workspace_path)
        assert workspace_path.exists()
        assert workspace_path.is_dir()

        # 检查初始文件是否创建
        assert (workspace_path / "todo.md").exists()
        assert (workspace_path / "_error.log").exists()
        assert (workspace_path / "task_metadata.json").exists()

    def test_load_task_metadata(self, manager):
        """测试加载任务元数据"""
        # 创建任务
        original_metadata = manager.create_task_workspace(
            title="测试任务",
            description="测试描述",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        # 加载任务元数据
        loaded_metadata = manager.load_task_metadata(original_metadata.task_id)

        assert loaded_metadata is not None
        assert loaded_metadata.task_id == original_metadata.task_id
        assert loaded_metadata.title == original_metadata.title
        assert loaded_metadata.description == original_metadata.description
        assert loaded_metadata.task_type == original_metadata.task_type

    def test_update_task_status(self, manager):
        """测试更新任务状态"""
        metadata = manager.create_task_workspace(
            title="测试任务",
            description="测试描述",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        # 更新状态
        success = manager.update_task_status(metadata.task_id, TaskStatus.IN_PROGRESS)
        assert success

        # 验证状态更新
        updated_metadata = manager.load_task_metadata(metadata.task_id)
        assert updated_metadata.status == TaskStatus.IN_PROGRESS

    def test_create_agent_file(self, manager):
        """测试创建智能体文件"""
        metadata = manager.create_task_workspace(
            title="测试任务",
            description="测试描述",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        # 创建智能体文件
        filename = manager.create_agent_file(
            task_id=metadata.task_id,
            step_number=1,
            agent_type=AgentType.COORDINATOR,
            task_type="Init",
            content="# 初始化内容\n\n这是协调器的初始化文件。",
        )

        assert filename is not None
        assert filename.startswith("01_Coordinator_Init_v1")

        # 检查文件是否创建
        file_path = Path(metadata.workspace_path) / filename
        assert file_path.exists()

        # 检查文件内容
        content = file_path.read_text(encoding="utf-8")
        assert "初始化内容" in content

    def test_update_todo_file(self, manager):
        """测试更新todo文件"""
        metadata = manager.create_task_workspace(
            title="测试任务",
            description="测试描述",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        new_content = "# 更新的待办清单\n\n- [x] 任务1完成\n- [ ] 任务2进行中"
        success = manager.update_todo_file(metadata.task_id, new_content)
        assert success

        # 检查文件内容
        todo_path = Path(metadata.workspace_path) / "todo.md"
        content = todo_path.read_text(encoding="utf-8")
        assert "更新的待办清单" in content

    def test_append_error_log(self, manager):
        """测试追加错误日志"""
        metadata = manager.create_task_workspace(
            title="测试任务",
            description="测试描述",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        error_message = "测试错误信息"
        success = manager.append_error_log(metadata.task_id, error_message)
        assert success

        # 检查错误日志
        error_log_path = Path(metadata.workspace_path) / "_error.log"
        content = error_log_path.read_text(encoding="utf-8")
        assert error_message in content

        # 检查错误计数更新
        updated_metadata = manager.load_task_metadata(metadata.task_id)
        assert updated_metadata.error_count == 1

    def test_get_task_recovery_info(self, manager):
        """测试获取任务恢复信息"""
        metadata = manager.create_task_workspace(
            title="测试任务",
            description="测试描述",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        # 创建一些文件
        manager.create_agent_file(
            task_id=metadata.task_id,
            step_number=1,
            agent_type=AgentType.COORDINATOR,
            task_type="Init",
            content="协调器初始化",
        )

        manager.update_task_status(metadata.task_id, TaskStatus.IN_PROGRESS)

        # 获取恢复信息
        recovery_info = manager.get_task_recovery_info(metadata.task_id)

        assert recovery_info is not None
        assert recovery_info["can_resume"] is True
        assert "task_metadata" in recovery_info
        assert "latest_files" in recovery_info
        assert "todo_content" in recovery_info
        assert "error_log" in recovery_info

    def test_list_tasks(self, manager):
        """测试列出任务"""
        # 创建多个任务
        task1 = manager.create_task_workspace(
            title="任务1", description="描述1", task_type=TaskType.TEST_CASE_GENERATION
        )

        task2 = manager.create_task_workspace(
            title="任务2",
            description="描述2",
            task_type=TaskType.TEST_SCRIPT_GENERATION,
        )

        # 列出任务
        tasks = manager.list_tasks()

        assert len(tasks) >= 2
        task_ids = [t.task_id for t in tasks]
        assert task1.task_id in task_ids
        assert task2.task_id in task_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
