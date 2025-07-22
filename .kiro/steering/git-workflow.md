# Git 版本管理规范

## 分支管理策略
- **主分支 (main/master)**: 稳定的生产代码，只接受经过测试的功能合并
- **开发分支 (develop)**: 集成分支，用于功能分支的集成和测试
- **功能分支 (feature/*)**: 每个新功能或修复都在独立分支上开发
- **修复分支 (hotfix/*)**: 紧急修复生产问题的分支

## 开发工作流程

### 1. 开始新功能开发
```bash
# 从主分支创建新的功能分支
git checkout main
git pull origin main
git checkout -b feature/功能名称-简短描述

# 例如：
git checkout -b feature/task-system-fixes
git checkout -b feature/add-user-authentication
```

### 2. 功能开发过程
```bash
# 定期提交代码
git add .
git commit -m "feat: 添加用户认证功能"

# 定期推送到远程分支
git push origin feature/功能名称-简短描述
```

### 3. 功能完成后的测试
```bash
# 运行完整测试套件
python -m pytest tests/ -v
./scripts/dev-deploy.sh test

# 代码质量检查
python -m black src/ tests/
python -m flake8 src/ tests/
```

### 4. 合并到主分支
```bash
# 确保功能分支是最新的
git checkout feature/功能名称-简短描述
git rebase main

# 切换到主分支并合并
git checkout main
git merge feature/功能名称-简短描述

# 推送到远程主分支
git push origin main

# 删除已完成的功能分支
git branch -d feature/功能名称-简短描述
git push origin --delete feature/功能名称-简短描述
```

## 提交信息规范
使用约定式提交（Conventional Commits）格式：

```
<类型>(<范围>): <描述>

[可选的正文]

[可选的脚注]
```

### 提交类型
- **feat**: 新功能
- **fix**: 修复bug
- **docs**: 文档更新
- **style**: 代码格式化（不影响功能）
- **refactor**: 代码重构
- **test**: 添加或修改测试
- **chore**: 构建过程或辅助工具的变动

### 示例
```bash
git commit -m "feat(agents): 添加新的研究员智能体"
git commit -m "fix(api): 修复任务状态更新问题"
git commit -m "docs: 更新API文档"
git commit -m "test: 添加协调器单元测试"
```

## 分支命名规范
- **功能分支**: `feature/功能描述` 或 `feature/issue-编号`
- **修复分支**: `fix/问题描述` 或 `hotfix/紧急修复描述`
- **文档分支**: `docs/文档更新描述`
- **重构分支**: `refactor/重构描述`

## 合并前检查清单
- [ ] 代码已通过所有测试
- [ ] 代码符合项目编码规范
- [ ] 已添加必要的测试用例
- [ ] 文档已更新（如需要）
- [ ] 功能已在开发环境验证
- [ ] 没有合并冲突
- [ ] 提交信息清晰明确

## 紧急修复流程
```bash
# 从主分支创建热修复分支
git checkout main
git checkout -b hotfix/紧急问题描述

# 修复问题并测试
# ... 修复代码 ...
python -m pytest tests/ -v

# 提交并合并
git commit -m "hotfix: 修复生产环境关键问题"
git checkout main
git merge hotfix/紧急问题描述
git push origin main

# 清理分支
git branch -d hotfix/紧急问题描述
```

## 最佳实践
- 保持功能分支小而专注，一个分支只做一件事
- 定期从主分支拉取更新，避免大的合并冲突
- 在合并前进行代码审查（如果是团队开发）
- 使用有意义的分支名和提交信息
- 删除已合并的功能分支，保持仓库整洁