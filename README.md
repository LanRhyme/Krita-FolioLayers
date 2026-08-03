<div align="center">

# Krita Folio Layers

<p>
  <a href="https://qm.qq.com/q/mtg1yNCi1q"><img alt="QQ" src="https://img.shields.io/badge/QQ-729283213-12B7F5?style=for-the-badge&logo=qq&logoColor=white"></a>
  <a href="https://afdian.com/a/LanRhyme" target="_blank" rel="noopener noreferrer"><img src="https://img.shields.io/badge/afdian-@LanRhyme-946ce6?style=for-the-badge&logo=afdian&logoColor=white" alt="afdian"></a>
</p>

Folio 风格图层管理 Docker，原生 Lucide 图标、分类混合模式、拖拽排序，内置 C++ 原生投影缩略图引擎

![Screenshot](https://raw.githubusercontent.com/LanRhyme/Krita-FolioLayers/main/screenshot.png)

</div>

## 功能特性

- **全功能图层管理**：新建各类图层（颜料/矢量/调整/滤镜/填充/克隆/文件）、复制、删除、图层组
- **图层排序**：按钮上移/下移，支持拖拽改变层级与嵌套关系
- **全分类混合模式菜单**：按 Normal / Darken / Lighten / Color / Composite 分类展示
- **颜色标记与不透明度**：横向 8 色标签色块选择器，原生不透明度条
- **图层树工具**：独显隔离、归组包裹、重命名、合并、拼合、栅格化
- **搜索筛选**：按图层名称快速过滤
- **悬停缩略图预览**：C++ 原生投影引擎渲染，缩略图与左侧层缩略图 100% 对齐
- **莫兰迪主题适配**：通过外部主题引擎动态注入配色
- **图层鼠标手势**：在图层项左划展开功能菜单
- **独显功能**：可选择图层独立显示，并清除所有效果，看快速切换，方便取色和查看

## 兼容性

| 操作系统 | Krita | Qt | 状态 |
| ---------- | ------- | ----- | ------ |
| Linux x86_64 | 5.x / 6.x | Qt5 / Qt6 | 完全支持，含预编译 `.so` |
| Windows x64 | 5.x / 6.x | Qt5 / Qt6 | 完全支持，含预编译 `.dll` |

插件本体为 Python 实现，兼容 Krita 5.0 及以上版本（PyQt5 / PyQt6 双引擎），跨平台运行
投影引擎为 C++ 预编译二进制，加载失败时自动回退纯 Python 模式

## 安装

### Linux

```bash
cp -r folio_layers ~/.local/share/krita/pykrita/
cp folio_layers.desktop ~/.local/share/krita/pykrita/folio_layers.desktop
```

重启 Krita，进入 设置 → 配置 Krita → Python 插件管理器，勾选 **Folio Layers**

### Windows

1. 将 `folio_layers` 文件夹复制到 `%APPDATA%\krita\pykrita\`
2. 将 `folio_layers.desktop` 复制为 `%APPDATA%\krita\pykrita\folio_layers.desktop`
3. 重启 Krita 并启用 **Folio Layers**

## 目录结构

- `folio_layers`：插件核心源码，内含预编译 `libfolio_projthumb.so` / `libfolio_projthumb*.dll`
- `native`：C++ 投影引擎源码、Krita 兼容头文件与构建脚本（`build.sh`）
- `folio_layers.desktop`：插件元数据清单，安装时复制为 `folio_layers.desktop`
- `LICENSE`：GPL-3.0

## 手动编译原生引擎（可选）

预编译二进制与运行时 Krita / Qt 不兼容时，可自行编译

```bash
bash native/build.sh
```

产物输出至 `native/build/libfolio_projthumb.so`，复制到 `folio_layers/` 即可

## 版权与许可

Copyright (C) 2026 LanRhyme
GNU General Public License version 3
