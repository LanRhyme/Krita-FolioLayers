# -*- coding: utf-8 -*-
"""
Folio Layer Docker Plugin Entry Point for Krita
"""

from .docker import LucideLayerDocker

DOCKER_ID = "folio_layers"

try:
    from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase

    Application = Krita.instance()
    try:
        dock_position = DockWidgetFactoryBase.DockRight
    except AttributeError:
        try:
            dock_position = DockWidgetFactoryBase.DockPosition.DockRight
        except AttributeError:
            dock_position = 1

    Application.addDockWidgetFactory(
        DockWidgetFactory(
            DOCKER_ID,
            dock_position,
            LucideLayerDocker
        )
    )
except ImportError:
    pass
