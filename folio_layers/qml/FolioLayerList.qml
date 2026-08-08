// FolioLayers QML 图层列表原型
// 验证目标：QQuickWidget 在 Krita 内的渲染、数位笔输入（DragHandler acceptedDevices）、拖拽让位动画
import QtQuick

ListView {
    id: list
    clip: true
    spacing: 2
    model: layerModel
    delegate: rowDelegate
    boundsBehavior: Flickable.StopAtBounds

    // 让位 / 移动动画（拖拽时其他行平滑让位）
    displaced: Transition {
        NumberAnimation { properties: "y"; duration: 180; easing.type: Easing.OutCubic }
    }
    move: Transition {
        NumberAnimation { properties: "y"; duration: 180; easing.type: Easing.OutCubic }
    }

    // 拖拽状态
    property int dragFrom: -1          // 被拖行当前索引（随模型移动更新）
    property int dragTo: -1            // 目标插入索引
    property bool dragActive: false
    property int hoveredIndex: -1

    // 落点回调（Python 执行 Krita 节点重排序）
    signal reorderRequested(int from, int to)
    // 行内交互回调
    signal toggleVisible(int rowIndex)
    signal rowClicked(int rowIndex)

    // 插入指示线（悬停目标行上沿）
    Rectangle {
        id: indicator
        height: 3
        radius: 1.5
        color: "#e0812f"
        opacity: 0
        visible: list.dragActive && list.dragTo >= 0 && list.dragTo != list.dragFrom
        y: indicatorY()
        function indicatorY() {
            if (!list.dragActive || list.dragTo < 0) return -99
            var dy = list.contentY + list.dragTo * (rowDelegateHeight + list.spacing) - 1.5
            return dy
        }
        width: parent.width - 12
        x: 6
        Behavior on y { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    }

    readonly property int rowDelegateHeight: 44

    Component {
        id: rowDelegate
        Item {
            id: row
            width: list.width
            height: list.rowDelegateHeight
            property bool isDragging: list.dragActive && list.dragFrom === index

            Rectangle {
                id: bg
                anchors.fill: parent
                radius: 6
                color: isDragging ? "#33ffffff"
                     : (list.hoveredIndex === index ? "#14ffffff" : "transparent")
                border.width: isDragging ? 1 : 0
                border.color: "#55ffffff"
            }

            // 拖起效果：轻微放大 + 投影
            transform: Scale { id: rowScale; xScale: 1; yScale: 1; origin.x: row.width/2; origin.y: row.height/2 }
            layer.enabled: isDragging
            layer.effect: isDragging ? shadow : null
            Component {
                id: shadow
                Item {
                    anchors.fill: parent
                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: "#000000"
                        opacity: 0.35
                        transform: Translate { y: 3 }
                        anchors.margins: 0
                    }
                }
            }

            // 缩略图占位（颜色块）
            Rectangle {
                id: thumb
                width: 32; height: 32
                radius: 4
                color: model.color
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 8
                opacity: model.visible ? 1.0 : 0.45
            }

            // 名称
            Text {
                id: nameTxt
                text: model.name
                color: model.visible ? "#e8e8e8" : "#888888"
                font.pixelSize: 13
                font.bold: model.locked
                elide: Text.ElideRight
                anchors.left: thumb.right
                anchors.leftMargin: 8
                anchors.right: eyeBtn.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
            }

            // 缩进
            Rectangle { x: 4 + 14 * model.depth; y: 0; width: 2; height: parent.height; color: "#22ffffff" }

            // 眼睛按钮
            Rectangle {
                id: eyeBtn
                width: 26; height: 26
                radius: 5
                color: eyeArea.pressed ? "#33ffffff" : "transparent"
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 6
                Text {
                    text: model.visible ? "👁" : "—"
                    color: model.visible ? "#e8e8e8" : "#666666"
                    font.pixelSize: 14
                    anchors.centerIn: parent
                }
                TapHandler {
                    id: eyeArea
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.Tablet
                    onTapped: list.toggleVisible(index)
                }
            }

            // 整行点击选中
            TapHandler {
                id: rowTap
                target: row
                acceptedDevices: PointerDevice.Mouse | PointerDevice.Tablet
                onTapped: list.rowClicked(index)
            }

            // —— 拖拽手势（鼠标 + 数位笔）——
            DragHandler {
                id: dragH
                target: null
                acceptedDevices: PointerDevice.Mouse | PointerDevice.Tablet
                acceptedButtons: Qt.LeftButton
                grabPermissions: PointerHandler.TakeOverForbidden

                onActiveChanged: {
                    if (active) {
                        // 按下开始拖拽
                        list.dragFrom = index
                        list.dragTo = index
                        list.dragActive = true
                        rowScale.xScale = 1.04; rowScale.yScale = 1.04
                        row.z = 10
                        list.interactive = false   // 禁止 ListView 自身滚动
                    } else {
                        // 松开：落点
                        list.dragActive = false
                        rowScale.xScale = 1; rowScale.yScale = 1
                        row.z = 0
                        list.interactive = true
                        if (list.dragFrom >= 0 && list.dragTo >= 0 && list.dragFrom !== list.dragTo) {
                            list.reorderRequested(list.dragFrom, list.dragTo)
                        }
                        list.dragFrom = -1
                        list.dragTo = -1
                        indicator.opacity = 0
                    }
                }
                onTranslationChanged: {
                    if (!active) return
                    // 计算目标索引：按行中心在列表中的位置
                    var rowH = list.rowDelegateHeight + list.spacing
                    var centerY = row.y + translation.y + list.rowDelegateHeight / 2
                    var to = Math.max(0, Math.min(list.count - 1, Math.floor(centerY / rowH)))
                    if (to !== list.dragTo) {
                        // 让位：模型移动 + displaced 动画
                        if (list.dragFrom !== to) {
                            layerModel.move(list.dragFrom, to)
                            list.dragFrom = to
                        }
                        list.dragTo = to
                        indicator.opacity = 1
                    }
                }
            }
        }
    }

    // hover 高亮（笔/鼠标悬停）
    HoverHandler {
        id: hoverH
        acceptedDevices: PointerDevice.Mouse | PointerDevice.Tablet
        onHoveredChanged: {
            if (!hovered) { list.hoveredIndex = -1 }
        }
        onPointChanged: {
            var p = point.position
            var i = Math.floor((p.y + list.contentY) / (list.rowDelegateHeight + list.spacing))
            if (i >= 0 && i < list.count) list.hoveredIndex = i
        }
    }
}
