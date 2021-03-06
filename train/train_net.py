import tools.find_mxnet
import mxnet as mx
import logging
import sys
import os
import importlib
import re
from dataset.iterator import DetRecordIter, DetIter
from train.metric import MultiBoxMetric
from evaluate.eval_metric import MApMetric, VOC07MApMetric
from config.config import cfg
from symbol.symbol_factory import get_symbol_train, get_symbol_train_concat
from tools.prepare_dataset import load_caltech


def convert_pretrained_concat(name, args):
    pretrained_resnet = os.path.join(os.getcwd(), '.', 'model', 'resnet50', 'resnet-50')
    epoch_resnet = 0
    sym_resnet, arg_params_resnet, aux_params_resnet = mx.model.load_checkpoint(pretrained_resnet, epoch_resnet)

    pretrained_two_stream_concat = os.path.join(os.getcwd(), '.', 'model', 'resnet50', 'resnet-50-Caltech-test', 'from_scratch', 'resnet-50')
    epoch_test = 1
    sym_ts_concat, arg_params_ts_concat, aux_params_ts_concat = mx.model.load_checkpoint(pretrained_two_stream_concat, epoch_test)

    for k in list(arg_params_ts_concat.keys()):
        if k.startswith('sub_'):
            k_origin = k[4:]
            if k_origin in list(arg_params_resnet.keys()):
                assert arg_params_ts_concat[k].shape == arg_params_resnet[k_origin].shape, 'arg params shape mismatch'
                arg_params_ts_concat[k] = arg_params_resnet[k_origin]
        else:
            if k in list(arg_params_resnet.keys()):
                if arg_params_ts_concat[k].shape == arg_params_resnet[k].shape:
                    arg_params_ts_concat[k] = arg_params_resnet[k]
                else:
                    print k
                    print(arg_params_ts_concat[k], arg_params_resnet[k])

    for k in list(aux_params_ts_concat.keys()):
        if k.startswith('sub_'):
            k_origin = k[4:]
            if k_origin in list(aux_params_resnet.keys()):
                assert aux_params_ts_concat[k].shape == aux_params_resnet[k_origin].shape, 'aux params shape mismatch'
                aux_params_ts_concat[k] = aux_params_resnet[k_origin]
        else:
            if k in list(aux_params_resnet.keys()):
                if aux_params_ts_concat[k].shape == aux_params_resnet[k].shape:
                    aux_params_ts_concat[k] = aux_params_resnet[k]
                else:
                    print k

    return arg_params_ts_concat, aux_params_ts_concat

def convert_pretrained(name, args):
    """
    Special operations need to be made due to name inconsistance, etc

    Parameters:
    ---------
    name : str
        pretrained model name
    args : dict
        loaded arguments

    Returns:
    ---------
    processed arguments as dict
    """
    # pretrained SSD_two_stream_w_four_layers
    pretrained_customized = os.path.join(os.getcwd(), '.', 'model', 'resnet50', 'resnet-50-Caltech_all-two_stream_w_four_layers', 'resnet-50')
    epoch_customized = 1
    sym_customized, arg_params_customized, aux_params_customized = mx.model.load_checkpoint(pretrained_customized, epoch_customized)

    # pretrained SSD_small
    pretrained_small = os.path.join(os.getcwd(), '.', 'model', 'resnet50', 'resnet-50-Caltech_h-gt20-lt50_v-gt0.2_customized-first-layer', 'resnet-50')
    epoch_small = 6
    sym_small, arg_params_small, aux_params_small = mx.model.load_checkpoint(pretrained_small, epoch_small)

    # pretrained SSD_large
    pretrained_large = os.path.join(os.getcwd(), '.', 'model', 'resnet50', 'resnet-50-Caltech_all_four_layers', 'resnet-50')
    epoch_large = 10
    sym_large, arg_params_large, aux_params_large = mx.model.load_checkpoint(pretrained_large, epoch_large)

    # copy params to sub-network: SSD_large + SSD_small
    new_arg_params = {}

    # large multi_feat 2 -> 3, 3 -> 4
    new_arg_params['multi_feat_3_conv_1x1_conv_bias'] = arg_params_large['multi_feat_2_conv_1x1_conv_bias']
    new_arg_params['multi_feat_3_conv_1x1_conv_weight'] = arg_params_large['multi_feat_2_conv_1x1_conv_weight']
    new_arg_params['multi_feat_3_conv_3x3_conv_bias'] = arg_params_large['multi_feat_2_conv_3x3_conv_bias']
    new_arg_params['multi_feat_3_conv_3x3_conv_weight'] = arg_params_large['multi_feat_2_conv_3x3_conv_weight']
    new_arg_params['multi_feat_3_conv_3x3_relu_loc_pred_conv_bias'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_loc_pred_conv_bias']
    new_arg_params['multi_feat_3_conv_3x3_relu_loc_pred_conv_weight'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_loc_pred_conv_weight']
    new_arg_params['multi_feat_3_conv_3x3_relu_cls_pred_conv_bias'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_cls_pred_conv_bias']
    new_arg_params['multi_feat_3_conv_3x3_relu_cls_pred_conv_weight'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_cls_pred_conv_weight']

    new_arg_params['multi_feat_4_conv_1x1_conv_bias'] = arg_params_large['multi_feat_3_conv_1x1_conv_bias']
    new_arg_params['multi_feat_4_conv_1x1_conv_weight'] = arg_params_large['multi_feat_3_conv_1x1_conv_weight']
    new_arg_params['multi_feat_4_conv_3x3_conv_bias'] = arg_params_large['multi_feat_3_conv_3x3_conv_bias']
    new_arg_params['multi_feat_4_conv_3x3_conv_weight'] = arg_params_large['multi_feat_3_conv_3x3_conv_weight']
    new_arg_params['multi_feat_4_conv_3x3_relu_loc_pred_conv_bias'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_loc_pred_conv_bias']
    new_arg_params['multi_feat_4_conv_3x3_relu_loc_pred_conv_weight'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_loc_pred_conv_weight']
    new_arg_params['multi_feat_4_conv_3x3_relu_cls_pred_conv_bias'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_cls_pred_conv_bias']
    new_arg_params['multi_feat_4_conv_3x3_relu_cls_pred_conv_weight'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_cls_pred_conv_weight']

    arg_params_large.pop('multi_feat_2_conv_1x1_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_1x1_conv_weight')
    arg_params_large.pop('multi_feat_2_conv_3x3_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_3x3_conv_weight')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_loc_pred_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_loc_pred_conv_weight')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_cls_pred_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_cls_pred_conv_weight')

    arg_params_large.pop('multi_feat_3_conv_1x1_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_1x1_conv_weight')
    arg_params_large.pop('multi_feat_3_conv_3x3_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_3x3_conv_weight')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_loc_pred_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_loc_pred_conv_weight')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_cls_pred_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_cls_pred_conv_weight')

    arg_params_small.pop('bn_data_beta')
    arg_params_small.pop('bn_data_gamma')
    new_arg_params['_plus28_cls_pred_conv_bias'] = arg_params_small['_plus12_cls_pred_conv_bias']
    new_arg_params['_plus28_cls_pred_conv_weight'] = arg_params_small['_plus12_cls_pred_conv_weight']
    new_arg_params['_plus28_loc_pred_conv_bias'] = arg_params_small['_plus12_loc_pred_conv_bias']
    new_arg_params['_plus28_loc_pred_conv_weight'] = arg_params_small['_plus12_loc_pred_conv_weight']
    arg_params_small.pop('_plus12_cls_pred_conv_bias')
    arg_params_small.pop('_plus12_cls_pred_conv_weight')
    arg_params_small.pop('_plus12_loc_pred_conv_bias')
    arg_params_small.pop('_plus12_loc_pred_conv_weight')
    for k, v in arg_params_large.iteritems():
        new_arg_params[k] = v
    for k, v in arg_params_small.iteritems():
        new_k = 'sub_' + k
        new_arg_params[new_k] = v


    """
    # copy params to sub-network: SSD_large + SSD_small with shared one shared stage(using SSD_large network layers)
    new_arg_params = {}

    # large multi_feat 1 -> 2, 2 -> 3
    #new_arg_params['multi_feat_2_conv_1x1_conv_bias'] = arg_params_large['multi_feat_1_conv_1x1_conv_bias']
    #new_arg_params['multi_feat_2_conv_1x1_conv_weight'] = arg_params_large['multi_feat_1_conv_1x1_conv_weight']
    #new_arg_params['multi_feat_2_conv_3x3_conv_bias'] = arg_params_large['multi_feat_1_conv_3x3_conv_bias']
    #new_arg_params['multi_feat_2_conv_3x3_conv_weight'] = arg_params_large['multi_feat_1_conv_3x3_conv_weight']
    #new_arg_params['multi_feat_2_conv_3x3_relu_loc_pred_conv_bias'] = arg_params_large[
    #    'multi_feat_1_conv_3x3_relu_loc_pred_conv_bias']
    #new_arg_params['multi_feat_2_conv_3x3_relu_loc_pred_conv_weight'] = arg_params_large[
    #    'multi_feat_1_conv_3x3_relu_loc_pred_conv_weight']
    #new_arg_params['multi_feat_2_conv_3x3_relu_cls_pred_conv_bias'] = arg_params_large[
    #    'multi_feat_1_conv_3x3_relu_cls_pred_conv_bias']
    #new_arg_params['multi_feat_2_conv_3x3_relu_cls_pred_conv_weight'] = arg_params_large[
    #    'multi_feat_1_conv_3x3_relu_cls_pred_conv_weight']
    #new_arg_params['multi_feat_3_conv_1x1_conv_bias'] = arg_params_large['multi_feat_2_conv_1x1_conv_bias']
    #new_arg_params['multi_feat_3_conv_1x1_conv_weight'] = arg_params_large['multi_feat_2_conv_1x1_conv_weight']
    #new_arg_params['multi_feat_3_conv_3x3_conv_bias'] = arg_params_large['multi_feat_2_conv_3x3_conv_bias']
    #new_arg_params['multi_feat_3_conv_3x3_conv_weight'] = arg_params_large['multi_feat_2_conv_3x3_conv_weight']
    #new_arg_params['multi_feat_3_conv_3x3_relu_loc_pred_conv_bias'] = arg_params_large[
    #    'multi_feat_2_conv_3x3_relu_loc_pred_conv_bias']
    #new_arg_params['multi_feat_3_conv_3x3_relu_loc_pred_conv_weight'] = arg_params_large[
    #    'multi_feat_2_conv_3x3_relu_loc_pred_conv_weight']
    #new_arg_params['multi_feat_3_conv_3x3_relu_cls_pred_conv_bias'] = arg_params_large[
    #    'multi_feat_2_conv_3x3_relu_cls_pred_conv_bias']
    #new_arg_params['multi_feat_3_conv_3x3_relu_cls_pred_conv_weight'] = arg_params_large[
    #    'multi_feat_2_conv_3x3_relu_cls_pred_conv_weight']

    #arg_params_large.pop('multi_feat_1_conv_1x1_conv_bias')
    #arg_params_large.pop('multi_feat_1_conv_1x1_conv_weight')
    #arg_params_large.pop('multi_feat_1_conv_3x3_conv_bias')
    #arg_params_large.pop('multi_feat_1_conv_3x3_conv_weight')
    #arg_params_large.pop('multi_feat_1_conv_3x3_relu_loc_pred_conv_bias')
    #arg_params_large.pop('multi_feat_1_conv_3x3_relu_loc_pred_conv_weight')
    #arg_params_large.pop('multi_feat_1_conv_3x3_relu_cls_pred_conv_bias')
    #arg_params_large.pop('multi_feat_1_conv_3x3_relu_cls_pred_conv_weight')

    #arg_params_large.pop('multi_feat_2_conv_1x1_conv_bias')
    #arg_params_large.pop('multi_feat_2_conv_1x1_conv_weight')
    #arg_params_large.pop('multi_feat_2_conv_3x3_conv_bias')
    #arg_params_large.pop('multi_feat_2_conv_3x3_conv_weight')
    #arg_params_large.pop('multi_feat_2_conv_3x3_relu_loc_pred_conv_bias')
    #arg_params_large.pop('multi_feat_2_conv_3x3_relu_loc_pred_conv_weight')
    #arg_params_large.pop('multi_feat_2_conv_3x3_relu_cls_pred_conv_bias')
    #arg_params_large.pop('multi_feat_2_conv_3x3_relu_cls_pred_conv_weight')

    # for 4-feature-layer large stream
    new_arg_params['multi_feat_2_conv_1x1_conv_bias'] = arg_params_large['multi_feat_2_conv_1x1_conv_bias']
    new_arg_params['multi_feat_2_conv_1x1_conv_weight'] = arg_params_large['multi_feat_2_conv_1x1_conv_weight']
    new_arg_params['multi_feat_2_conv_3x3_conv_bias'] = arg_params_large['multi_feat_2_conv_3x3_conv_bias']
    new_arg_params['multi_feat_2_conv_3x3_conv_weight'] = arg_params_large['multi_feat_2_conv_3x3_conv_weight']
    new_arg_params['multi_feat_2_conv_3x3_relu_loc_pred_conv_bias'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_loc_pred_conv_bias']
    new_arg_params['multi_feat_2_conv_3x3_relu_loc_pred_conv_weight'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_loc_pred_conv_weight']
    new_arg_params['multi_feat_2_conv_3x3_relu_cls_pred_conv_bias'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_cls_pred_conv_bias']
    new_arg_params['multi_feat_2_conv_3x3_relu_cls_pred_conv_weight'] = arg_params_large[
        'multi_feat_2_conv_3x3_relu_cls_pred_conv_weight']

    new_arg_params['multi_feat_3_conv_1x1_conv_bias'] = arg_params_large['multi_feat_3_conv_1x1_conv_bias']
    new_arg_params['multi_feat_3_conv_1x1_conv_weight'] = arg_params_large['multi_feat_3_conv_1x1_conv_weight']
    new_arg_params['multi_feat_3_conv_3x3_conv_bias'] = arg_params_large['multi_feat_3_conv_3x3_conv_bias']
    new_arg_params['multi_feat_3_conv_3x3_conv_weight'] = arg_params_large['multi_feat_3_conv_3x3_conv_weight']
    new_arg_params['multi_feat_3_conv_3x3_relu_loc_pred_conv_bias'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_loc_pred_conv_bias']
    new_arg_params['multi_feat_3_conv_3x3_relu_loc_pred_conv_weight'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_loc_pred_conv_weight']
    new_arg_params['multi_feat_3_conv_3x3_relu_cls_pred_conv_bias'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_cls_pred_conv_bias']
    new_arg_params['multi_feat_3_conv_3x3_relu_cls_pred_conv_weight'] = arg_params_large[
        'multi_feat_3_conv_3x3_relu_cls_pred_conv_weight']

    arg_params_large.pop('multi_feat_2_conv_1x1_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_1x1_conv_weight')
    arg_params_large.pop('multi_feat_2_conv_3x3_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_3x3_conv_weight')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_loc_pred_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_loc_pred_conv_weight')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_cls_pred_conv_bias')
    arg_params_large.pop('multi_feat_2_conv_3x3_relu_cls_pred_conv_weight')

    arg_params_large.pop('multi_feat_3_conv_1x1_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_1x1_conv_weight')
    arg_params_large.pop('multi_feat_3_conv_3x3_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_3x3_conv_weight')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_loc_pred_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_loc_pred_conv_weight')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_cls_pred_conv_bias')
    arg_params_large.pop('multi_feat_3_conv_3x3_relu_cls_pred_conv_weight')

    arg_params_small.pop('bn_data_beta')
    arg_params_small.pop('bn_data_gamma')
    # _plus42 for one shared stage and _plus38 for two shared stages
    new_arg_params['_plus38_cls_pred_conv_bias'] = arg_params_small['_plus12_cls_pred_conv_bias']
    new_arg_params['_plus38_cls_pred_conv_weight'] = arg_params_small['_plus12_cls_pred_conv_weight']
    new_arg_params['_plus38_loc_pred_conv_bias'] = arg_params_small['_plus12_loc_pred_conv_bias']
    new_arg_params['_plus38_loc_pred_conv_weight'] = arg_params_small['_plus12_loc_pred_conv_weight']
    arg_params_small.pop('_plus12_cls_pred_conv_bias')
    arg_params_small.pop('_plus12_cls_pred_conv_weight')
    arg_params_small.pop('_plus12_loc_pred_conv_bias')
    arg_params_small.pop('_plus12_loc_pred_conv_weight')

    # for 4 layer large stream
    arg_params_large.pop('_plus12_cls_pred_conv_bias')
    arg_params_large.pop('_plus12_cls_pred_conv_weight')
    arg_params_large.pop('_plus12_loc_pred_conv_bias')
    arg_params_large.pop('_plus12_loc_pred_conv_weight')

    for k, v in arg_params_large.iteritems():
        new_arg_params[k] = v
    for k, v in arg_params_small.iteritems():
        new_k = 'sub_' + k
        new_arg_params[new_k] = v
    """

    return new_arg_params

def get_lr_scheduler(learning_rate, lr_refactor_step, lr_refactor_ratio,
                     num_example, batch_size, begin_epoch):
    """
    Compute learning rate and refactor scheduler

    Parameters:
    ---------
    learning_rate : float
        original learning rate
    lr_refactor_step : comma separated str
        epochs to change learning rate
    lr_refactor_ratio : float
        lr *= ratio at certain steps
    num_example : int
        number of training images, used to estimate the iterations given epochs
    batch_size : int
        training batch size
    begin_epoch : int
        starting epoch

    Returns:
    ---------
    (learning_rate, mx.lr_scheduler) as tuple
    """
    assert lr_refactor_ratio > 0
    iter_refactor = [int(r) for r in lr_refactor_step.split(',') if r.strip()]
    if lr_refactor_ratio >= 1:
        return (learning_rate, None)
    else:
        lr = learning_rate
        epoch_size = num_example // batch_size
        for s in iter_refactor:
            if begin_epoch >= s:
                lr *= lr_refactor_ratio
        if lr != learning_rate:
            logging.getLogger().info("Adjusted learning rate to {} for epoch {}".format(lr, begin_epoch))
        steps = [epoch_size * (x - begin_epoch) for x in iter_refactor if x > begin_epoch]
        if not steps:
            return (lr, None)
        lr_scheduler = mx.lr_scheduler.MultiFactorScheduler(step=steps, factor=lr_refactor_ratio)
        return (lr, lr_scheduler)

def train_net(net, train_path, num_classes, batch_size,
              data_shape, mean_pixels, resume, finetune, pretrained, epoch,
              prefix, ctx, begin_epoch, end_epoch, frequent, learning_rate,
              momentum, weight_decay, lr_refactor_step, lr_refactor_ratio,
              freeze_layer_pattern='',
              num_example=10000, label_pad_width=350,
              nms_thresh=0.45, force_nms=False, ovp_thresh=0.5,
              use_difficult=False, class_names=None,
              voc07_metric=False, nms_topk=400, force_suppress=False,
              train_list="", val_path="", val_list="", iter_monitor=0,
              monitor_pattern=".*", log_file=None):
    """
    Wrapper for training phase.

    Parameters:
    ----------
    net : str
        symbol name for the network structure
    train_path : str
        record file path for training
    num_classes : int
        number of object classes, not including background
    batch_size : int
        training batch-size
    data_shape : int or tuple
        width/height as integer or (3, height, width) tuple
    mean_pixels : tuple of floats
        mean pixel values for red, green and blue
    resume : int
        resume from previous checkpoint if > 0
    finetune : int
        fine-tune from previous checkpoint if > 0
    pretrained : str
        prefix of pretrained model, including path
    epoch : int
        load epoch of either resume/finetune/pretrained model
    prefix : str
        prefix for saving checkpoints
    ctx : [mx.cpu()] or [mx.gpu(x)]
        list of mxnet contexts
    begin_epoch : int
        starting epoch for training, should be 0 if not otherwise specified
    end_epoch : int
        end epoch of training
    frequent : int
        frequency to print out training status
    learning_rate : float
        training learning rate
    momentum : float
        trainig momentum
    weight_decay : float
        training weight decay param
    lr_refactor_ratio : float
        multiplier for reducing learning rate
    lr_refactor_step : comma separated integers
        at which epoch to rescale learning rate, e.g. '30, 60, 90'
    freeze_layer_pattern : str
        regex pattern for layers need to be fixed
    num_example : int
        number of training images
    label_pad_width : int
        force padding training and validation labels to sync their label widths
    nms_thresh : float
        non-maximum suppression threshold for validation
    force_nms : boolean
        suppress overlaped objects from different classes
    train_list : str
        list file path for training, this will replace the embeded labels in record
    val_path : str
        record file path for validation
    val_list : str
        list file path for validation, this will replace the embeded labels in record
    iter_monitor : int
        monitor internal stats in networks if > 0, specified by monitor_pattern
    monitor_pattern : str
        regex pattern for monitoring network stats
    log_file : str
        log to file if enabled
    """
    if net == 'resnet101_two_stream' or net == 'resnetsub101_test' or \
            net == 'resnetsub101_one_shared' or net == 'resnetsub101_two_shared' or \
            net == 'resnet50_two_stream_w_four_layers' \
            and resume == -1 and pretrained is not False:
        convert_model = True
    else:
        convert_model = False

    if net == 'resnet50_two_stream' \
            and resume == -1 \
            and pretrained is not False:
        convert_model_concat = True
    else:
        convert_model_concat = False


    # set up logger
    logging.basicConfig()
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if log_file:
        fh = logging.FileHandler(log_file)
        logger.addHandler(fh)

    # check args
    num_channel = 3
    if isinstance(data_shape, int):
        data_shape = (num_channel, data_shape, data_shape)
    if isinstance(data_shape, list):
        data_shape = (num_channel, data_shape[0], data_shape[1])
    #assert len(data_shape) == 3 and data_shape[0] == 3
    if prefix.endswith('_'):
        prefix += '_' + str(data_shape[1])

    if isinstance(mean_pixels, (int, float)):
        mean_pixels = [mean_pixels, mean_pixels, mean_pixels]
    assert len(mean_pixels) == 3, "must provide all RGB mean values"

    #train_iter = DetRecordIter(train_path, batch_size, data_shape, mean_pixels=mean_pixels,
    #    label_pad_width=label_pad_width, path_imglist=train_list, **cfg.train)

    # load imdb
    curr_path = os.path.abspath(os.path.dirname(__file__))
    imdb_train = load_caltech(image_set='train',
                        caltech_path=os.path.join(curr_path, '..', 'data', 'caltech-pedestrian-dataset-converter'),
                        shuffle=True)
    train_iter = DetIter(imdb_train, batch_size, (data_shape[1], data_shape[2]), \
                         mean_pixels=mean_pixels, rand_samplers=[], \
                         rand_mirror=False, shuffle=False, rand_seed=None, \
                         is_train=True, max_crop_trial=50)

    if val_path:
        #val_iter = DetRecordIter(val_path, batch_size, data_shape, mean_pixels=mean_pixels,
        #    label_pad_width=label_pad_width, path_imglist=val_list, **cfg.valid)
        imdb_val = load_caltech(image_set='val',
                            caltech_path=os.path.join(curr_path, '..', 'data', 'caltech-pedestrian-dataset-converter'),
                            shuffle=False)
        val_iter = DetIter(imdb_val, batch_size, (data_shape[1], data_shape[2]), \
                           mean_pixels=mean_pixels, rand_samplers=[], \
                           rand_mirror=False, shuffle=False, rand_seed=None, \
                           is_train=True, max_crop_trial=50)
    else:
        val_iter = None

    # load symbol
    #net = get_symbol_train(net, data_shape[1], num_classes=num_classes,
    net = get_symbol_train_concat(net, data_shape[1], num_classes=num_classes,
                           nms_thresh=nms_thresh, force_suppress=force_suppress, nms_topk=nms_topk)

    # define layers with fixed weight/bias
    if freeze_layer_pattern.strip():
        re_prog = re.compile(freeze_layer_pattern)
        fixed_param_names = [name for name in net.list_arguments() if re_prog.match(name)]
    else:
        fixed_param_names = None

    # load pretrained or resume from previous state
    ctx_str = '('+ ','.join([str(c) for c in ctx]) + ')'
    if resume > 0:
        logger.info("Resume training with {} from epoch {}"
            .format(ctx_str, resume))
        _, args, auxs = mx.model.load_checkpoint(prefix, resume)
        begin_epoch = resume
    elif finetune > 0:
        logger.info("Start finetuning with {} from epoch {}"
            .format(ctx_str, finetune))
        _, args, auxs = mx.model.load_checkpoint(prefix, finetune)
        begin_epoch = finetune
        # check what layers mismatch with the loaded parameters
        exe = net.simple_bind(mx.cpu(), data=(1, 3, 300, 300), label=(1, 1, 5), grad_req='null')
        arg_dict = exe.arg_dict
	fixed_param_names = []
        for k, v in arg_dict.items():
            if k in args:
                if v.shape != args[k].shape:
                    del args[k]
                    logging.info("Removed %s" % k)
                else:
		    if not 'pred' in k:
		    	fixed_param_names.append(k)
    elif pretrained:
        logger.info("Start training with {} from pretrained model {}"
            .format(ctx_str, pretrained))
        _, args, auxs = mx.model.load_checkpoint(pretrained, epoch)
        if convert_model:
            args = convert_pretrained(pretrained, args)
        if convert_model_concat:
            args, auxs = convert_pretrained_concat(pretrained, args)
    else:
        logger.info("Experimental: start training from scratch with {}"
            .format(ctx_str))
        args = None
        auxs = None
        fixed_param_names = None

    # helper information
    if fixed_param_names:
        logger.info("Freezed parameters: [" + ','.join(fixed_param_names) + ']')

    # init training module
    #mod = mx.mod.Module(net, label_names=('label',), logger=logger, context=ctx,
    mod = mx.mod.Module(net, label_names=('label', 'label2'), logger=logger, context=ctx,
                        fixed_param_names=fixed_param_names)

    # fit parameters
    batch_end_callback = mx.callback.Speedometer(train_iter.batch_size, frequent=frequent)
    epoch_end_callback = mx.callback.do_checkpoint(prefix)
    learning_rate, lr_scheduler = get_lr_scheduler(learning_rate, lr_refactor_step,
        lr_refactor_ratio, num_example, batch_size, begin_epoch)
    optimizer_params={'learning_rate':learning_rate,
                      'momentum':momentum,
                      'wd':weight_decay,
                      'lr_scheduler':lr_scheduler,
                      'clip_gradient':None,
                      'rescale_grad': 1.0 / len(ctx) if len(ctx) > 0 else 1.0 }
    monitor = mx.mon.Monitor(iter_monitor, pattern=monitor_pattern) if iter_monitor > 0 else None

    # run fit net, every n epochs we run evaluation network to get mAP
    if voc07_metric:
        #valid_metric = VOC07MApMetric(ovp_thresh, use_difficult, class_names, pred_idx=3)
        valid_metric = VOC07MApMetric(ovp_thresh, use_difficult, class_names, pred_idx=[0, 1],
                              output_names=['det_out_output', 'det_out2_output'], label_names=['label', 'label2'])
    else:
        #valid_metric = MApMetric(ovp_thresh, use_difficult, class_names, pred_idx=3)
        valid_metric = MApMetric(ovp_thresh, use_difficult, class_names, pred_idx=[0, 1],
                             output_names=['det_out_output', 'det_out2_output'], label_names=['label', 'label2'])

    # messager is activated in base_module
    mod.fit(train_iter,
            val_iter,
            eval_metric=MultiBoxMetric(),
            validation_metric=valid_metric,
            batch_end_callback=batch_end_callback,
            epoch_end_callback=epoch_end_callback,
            optimizer='sgd',
            optimizer_params=optimizer_params,
            begin_epoch=begin_epoch,
            num_epoch=end_epoch,
            initializer=mx.init.Xavier(),
            arg_params=args,
            aux_params=auxs,
            allow_missing=True,
            monitor=monitor)
