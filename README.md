# Krita Folio Layers

A Folio-style layer panel Docker for Krita, with native Lucide icons, categorized blending modes, and drag-and-drop layer sorting

## 功能特性

- **全功能图层管理**：新建各类图层（颜料/矢量/调整/滤镜/填充/克隆/文件）、复制、删除、图层组
- **图层排序**：按钮上移/下移，支持拖拽改变层级与嵌套关系
- **全分类混合模式菜单**：按 Normal / Darken / Lighten / Color / Composite 分类展示
- **颜色标记与不透明度**：横向 8 色标签色块选择器，原生不透明度条
- **图层树工具**：独显隔离、归组包裹、重命名、合并、拼合、栅格化
- **搜索筛选**：按图层名称快速过滤
- **悬停缩略图预览**
- **莫兰迪主题适配**：通过外部主题引擎动态注入配色

## 兼容性说明

本插件为纯 Python 实现，兼容 **Krita 5.0 及以上版本**（支持 PyQt5 与 PyQt6 双引擎环境），跨平台运行

## 目录结构

- `folio_layers`: 插件核心源码目录
- `folio_layers.desktop`: 插件元数据清单

## 版权与许可 (Copyright & License)

Copyright (C) 2026 LanRhyme
GNU General Public License version 3
