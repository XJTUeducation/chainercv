import copy
import numpy as np

from chainer import reporter
import chainer.training.extensions

from chainercv.evaluations import eval_detection_coco
from chainercv.utils import apply_to_iterator


class DetectionCOCOEvaluator(chainer.training.extensions.Evaluator):

    """An extension that evaluates a detection model by MS COCO metric.

    This extension iterates over an iterator and evaluates the prediction
    results.
    The results consist of average precisions (APs) and average
    recalls (ARs) as well as the mean of each (mean average precision and mean
    average recall).
    This extension reports the following values with keys.
    Please note that if
    :obj:`label_names` is not specified, only the mAP and  mAR are reported.

    .. csv-table::
        :header: key, description

        ap/iou=0.50:0.95/area=all/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_1]_
        ap/iou=0.50/area=all/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_1]_
        ap/iou=0.75/area=all/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_1]_
        ap/iou=0.50:0.95/area=small/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_1]_
        ap/iou=0.50:0.95/area=medium/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_1]_
        ap/iou=0.50:0.95/area=large/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_1]_
        ar/iou=0.50:0.95/area=all/maxDets=1/<label_names[l]>, \
            [#coco_det_ext_2]_
        ar/iou=0.50/area=all/maxDets=10/<label_names[l]>, \
            [#coco_det_ext_2]_
        ar/iou=0.75/area=all/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_2]_
        ar/iou=0.50:0.95/area=small/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_2]_
        ar/iou=0.50:0.95/area=medium/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_2]_
        ar/iou=0.50:0.95/area=large/maxDets=100/<label_names[l]>, \
            [#coco_det_ext_2]_
        map/iou=0.50:0.95/area=all/maxDets=100, \
            [#coco_det_ext_3]_
        map/iou=0.50/area=all/maxDets=100, \
            [#coco_det_ext_3]_
        map/iou=0.75/area=all/maxDets=100, \
            [#coco_det_ext_3]_
        map/iou=0.50:0.95/area=small/maxDets=100, \
            [#coco_det_ext_3]_
        map/iou=0.50:0.95/area=medium/maxDets=100, \
            [#coco_det_ext_3]_
        map/iou=0.50:0.95/area=large/maxDets=100, \
            [#coco_det_ext_3]_
        ar/iou=0.50:0.95/area=all/maxDets=1, \
            [#coco_det_ext_4]_
        ar/iou=0.50/area=all/maxDets=10, \
            [#coco_det_ext_4]_
        ar/iou=0.75/area=all/maxDets=100, \
            [#coco_det_ext_4]_
        ar/iou=0.50:0.95/area=small/maxDets=100, \
            [#coco_det_ext_4]_
        ar/iou=0.50:0.95/area=medium/maxDets=100, \
            [#coco_det_ext_4]_
        ar/iou=0.50:0.95/area=large/maxDets=100, \
            [#coco_det_ext_4]_

    .. [#coco_det_ext_1] Average precision for class \
        :obj:`label_names[l]`, where :math:`l` is the index of the class. \
        If class :math:`l` does not exist in either :obj:`pred_labels` or \
        :obj:`gt_labels`, the corresponding value is set to :obj:`numpy.nan`.
    .. [#coco_det_ext_2] Average recall for class \
        :obj:`label_names[l]`, where :math:`l` is the index of the class. \
        If class :math:`l` does not exist in either :obj:`pred_labels` or \
        :obj:`gt_labels`, the corresponding value is set to :obj:`numpy.nan`.
    .. [#coco_det_ext_3] The average of average precisions over classes.
    .. [#coco_det_ext_4] The average of average recalls over classes.

    Args:
        iterator (chainer.Iterator): An iterator. Each sample should be
            following tuple :obj:`img, bbox, label, area, crowded`.
        target (chainer.Link): A detection link. This link must have
            :meth:`predict` method that takes a list of images and returns
            :obj:`bboxes`, :obj:`labels` and :obj:`scores`.
        label_names (iterable of strings): An iterable of names of classes.
            If this value is specified, average precision and average
            recalls for each class are reported.

    """

    trigger = 1, 'epoch'
    default_name = 'validation'
    priority = chainer.training.PRIORITY_WRITER

    def __init__(
            self, iterator, target,
            label_names=None):
        super(DetectionCOCOEvaluator, self).__init__(
            iterator, target)
        self.label_names = label_names

    def evaluate(self):
        iterator = self._iterators['main']
        target = self._targets['main']

        if hasattr(iterator, 'reset'):
            iterator.reset()
            it = iterator
        else:
            it = copy.copy(iterator)

        in_values, out_values, rest_values = apply_to_iterator(
            target.predict, it)
        # delete unused iterators explicitly
        del in_values

        pred_bboxes, pred_labels, pred_scores = out_values

        if len(rest_values) != 4:
            raise ValueError('the dataset should return '
                             'gt_bboxes, gt_labels, gt_areas, gt_crowdeds')
        gt_bboxes, gt_labels, gt_areas, gt_crowdeds =\
            rest_values

        result = eval_detection_coco(
            pred_bboxes, pred_labels, pred_scores,
            gt_bboxes, gt_labels, gt_areas, gt_crowdeds)

        report = {}
        for key in result.keys():
            if key.startswith('map') or key.startswith('mar'):
                report[key] = result[key]

        if self.label_names is not None:
            for key in result.keys():
                if key.startswith('ap') or key.startswith('ar'):
                    for l, label_name in enumerate(self.label_names):
                        report_key = '{}/{:s}'.format(key, label_name)
                        print(result[key], key, l)
                        try:
                            report[report_key] = result[key][l]
                        except IndexError:
                            report[report_key] = np.nan

        observation = {}
        with reporter.report_scope(observation):
            reporter.report(report, target)
        return observation