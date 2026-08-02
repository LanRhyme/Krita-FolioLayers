# -*- coding: utf-8 -*-
"""
Folio Layer Docker Plugin Entry Point for Krita
"""

from .docker import FolioLayersDocker

DOCKER_ID = "folio_layers"

try:
    from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase

    Application = Krita.instance()
    try:
        dock_position = DockWidgetFactoryBase.DockBottom
    except AttributeError:
        try:
            dock_position = DockWidgetFactoryBase.DockPosition.DockBottom
        except AttributeError:
            dock_position = 2

    Application.addDockWidgetFactory(
        DockWidgetFactory(
            DOCKER_ID,
            dock_position,
            FolioLayersDocker
        )
    )
except ImportError:
    pass
