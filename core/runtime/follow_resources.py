"""Explicit reference/navigation wall selection using existing map versions."""
import hashlib
from pathlib import Path
import cv2
import numpy as np
from core.map_editing.version_storage import load_wall_version_catalog
from core.localization.map_runtime import MapRuntime


def load_follow_maps(config):
    source=Path(config.map_path)
    with np.load(source,allow_pickle=False) as data: base=data['wall_layer']
    catalog=load_wall_version_catalog(source.parent,base)
    reference=base if config.reference_walls=='base' else catalog.active_wall_layer
    nav=(catalog.active_wall_layer>0).astype(np.uint8)
    digest=hashlib.sha256()
    for layer in (reference,nav):
        digest.update(str(layer.shape).encode('ascii'))
        digest.update(np.ascontiguousarray(layer>0,dtype=np.uint8).tobytes())
    version=digest.hexdigest()
    if config.clearance:
        k=2*config.clearance+1
        nav=cv2.dilate(nav,np.ones((k,k),np.uint8))
    return MapRuntime.from_wall_layer(reference,map_id=config.map_id,map_version=version),nav
