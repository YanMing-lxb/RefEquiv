# RefEquiv - 制冷剂等效气相物性计算器

## 简介

RefEquiv（制冷剂等效气相物性计算器）是一个基于 REFPROP 物性数据库的两相制冷剂等效单相物性计算工具，针对温度滑移区间的等效气相建模：

- 采用对称模型（EMT）计算等效导热系数
- 支持 McAdams 或 Cicchitti 粘度模型
- 提供多种等效比热容方法

## 使用方法

### 运行程序

直接运行 `RefEquiv.exe` 进入交互模式，程序会提示输入：
- 制冷剂名称
- 压力值（MPa，多个用空格分隔）
- 干度离散点数
- 粘度模型选择
- 等效比热容方法选择

## 开发构建

### 环境准备

确保已安装 uv：

```bash
pip install uv
```

安装依赖：

```bash
uv sync --dev
```

### 打包为 exe

```bash
uv run tools/pack.py
```

或使用 Make：

```bash
make build
```

### 清理临时文件

```bash
uv run tools/pack.py --clean
```

或使用 Make：

```bash
make clean
```

## 版本历史

详见 [CHANGELOG.md](./CHANGELOG.md)

## 许可证

GPL-3.0-or-later