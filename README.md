# Krita Folio Layers

**Folio 风格的图层管理 Docker**，为 Krita 提供带 Lucide 图标的原生图层面板，支持全分类混合模式菜单、颜色标记、不透明度条、缩略图预览及拖拽排序

## 功能特性

- **图层 CRUD**：新建（颜料/矢量/调整/滤镜/填充/克隆/文件图层）、复制、删除、图层组
- **图层排序**：上移/下移按钮，支持拖拽改变图层顺序和嵌套关系
- **全分类混合模式菜单**：按 Normal、Darken、Lighten、Color、Composite 分类展示全部混合模式
- **不透明度条**：原生 QSlider 风格不透明度控件，实时更新
- **颜色标记**：横向色块选择器，8 色标签快速标记图层
- **图层树管理**：独显/隔离图层、归组包裹、重命名、合并到下层、拼合、栅格化
- **搜索筛选**：按图层名称搜索过滤
- **悬停预览**：鼠标悬停显示图层缩略图浮窗
- **拖拽排序**：自定义 TreeWidget 支持拖拽改变图层层级，事件转发至 Krita 原生 API
- **自适应主题**：通过外部 `morandi-gen.py` 动态注入莫兰迪配色
- **持久化设置**：通过 `QSettings` 保存用户偏好

## 系统及 Krita 版本支持

| 操作系统 | Krita 版本 | Qt 版本 | 状态 |
|----------|------------|--------|------|
| Linux x86_64 | 6.0 | Qt 6 | ✅ 完全支持 |
| Windows x64 | 5.3+ | Qt 5/6 | ✅ 支持（Python 插件，无需编译） |
| macOS | 任意 | 任意 | ✅ 支持 |

> 本插件为纯 Python 实现，无 C++ Bridge 依赖，跨平台开箱即用

## 安装指南

### Linux

```bash
git clone https://github.com/LanRhyme/Krita-FolioLayers.git
cp -r Krita-FolioLayers/folio_layers ~/.local/share/krita/pykrita/
# 重启 Krita，在 Python 插件管理器中启用 "Folio Layers"
```

### Windows

1. 下载或克隆本仓库
2. 将 `folio_layers` 文件夹复制到 `%APPDATA%\krita\pykrita\`
3. 重启 Krita 并启用插件

### 手动部署

将插件打包后放置到 Krita 的 Python 插件目录，或通过 "配置 Krita → 插件" 加载

## 使用说明

插件启用后，可通过 **设置 → 面板列表 → Folio Layers** 打开 Docker

## 项目结构

```
folio_layers/
├── __init__.py                 # 插件入口，注册 Docker
├── docker.py                   # Docker 容器，整合所有功能
├── layer_item.py               # 图层行控件（按钮、缩略图、拖拽）
├── hover_preview.py            # 悬停缩略图浮窗
├── blending_modes.py           # 分类混合模式菜单构建
├── color_label_popup.py        # 颜色标记横向色块选择器
├── opacity_bar.py              # 不透明度条控件
├── config.py                   # 持久化配置管理（QSettings）
├── settings_dialog.py          # 偏好设置对话框
├── theme.py                    # 莫兰迪主题接口
├── lucide_icons.py             # Lucide SVG 图标加载
├── qt_compat.py                # Qt5/Qt6 兼容层
└── README.md
```

## 许可证

本插件采用 **GNU GPL v3.0** 许可证发布，详见仓库根目录的 `LICENSE` 文件。使用、修改或分发本插件必须遵守 GPL‑3.0 的条款

---

> 若有任何问题或需求，请在 GitHub Issues 提交
