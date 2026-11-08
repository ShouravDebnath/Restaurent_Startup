"""Explicit reviewed adapters only; no plugin import paths or network resolution."""

from restaurant_edge.detectors.onnx_detector import ModelUnavailable, OnnxDetector
from restaurant_edge.detectors.rfdetr import RfDetrNano


def detector_for(artifact):
    factories = {'yolox_tiny': OnnxDetector, 'rfdetr_nano': RfDetrNano}
    factory = factories.get(artifact.model_id)
    if factory is None:
        raise ModelUnavailable('MODEL_APPROVAL_REQUIRED')
    return factory(artifact)
