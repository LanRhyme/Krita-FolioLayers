def get_native_model():
    from krita import Krita
    main_window = Krita.instance().activeWindow().qwindow()
    layer_box = main_window.findChild(QDockWidget, "LayerBox")
    list_layers = layer_box.findChild(QTreeView, "listLayers")
    return list_layers.model()
