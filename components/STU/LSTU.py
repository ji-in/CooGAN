#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#############################################################
# File: LSTU.py
# Created Date: Wednesday February 26th 2020
# Author: Chen Xuanhong
# Email: chenxuanhongzju@outlook.com
# Last Modified:  Wednesday, 26th February 2020 12:02:19 am
# Modified By: Chen Xuanhong
# Copyright (c) 2020 Shanghai Jiao Tong University
#############################################################

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from functools import partial

import tensorflow as tf
import tensorflow.contrib.slim as slim
import tflib as tl


conv = partial(slim.conv2d, activation_fn=None)
dconv = partial(slim.conv2d_transpose, activation_fn=None)
sigmoid = tf.nn.sigmoid
tanh = tf.nn.tanh
batch_norm = partial(slim.batch_norm, scale=True, updates_collections=None)
instance_norm = slim.instance_norm

MAX_DIM = 64 * 16

def ConvGRUCell(in_data, state, out_channel, is_training=True, kernel_size=3, norm='none', pass_state='lstate'):
    if norm == 'bn':
        norm_fn = partial(batch_norm, is_training=is_training)
    elif norm == 'in':
        norm_fn = instance_norm
    else:
        norm_fn = None
    gate = partial(conv, normalizer_fn=norm_fn, activation_fn=sigmoid)
    info = partial(conv, normalizer_fn=norm_fn, activation_fn=tanh)
    with tf.name_scope('ConvGRUCell'):
        state_ = dconv(state, out_channel, 4, 2)  # upsample and make `channel` identical to `out_channel`
        # reset_gate = gate(tf.concat([in_data, state_], axis=3), out_channel, kernel_size)
        update_gate = gate(tf.concat([in_data, state_], axis=3), out_channel, kernel_size)
        # new_state = reset_gate * state_
        new_info    = info(tf.concat([in_data, state_], axis=3), out_channel, kernel_size)
        output = (1-update_gate)*state_ + update_gate*new_info
        if pass_state == 'gru':
            return output, output
        elif pass_state == 'direct':
            return output, state_
        else: # 'stu'
            return output, new_info

def Gstu(zs, _a, dim=64, n_layers=1, inject_layers=0, is_training=True, kernel_size=3, norm='none', pass_state='stu'):
    def _concat(z, z_, _a):
        feats = [z]
        if z_ is not None:
            feats.append(z_)
        if _a is not None:
            _a = tf.reshape(_a, [-1, 1, 1, tl.shape(_a)[-1]])
            _a = tf.tile(_a, [1, tl.shape(z)[1], tl.shape(z)[2], 1])
            feats.append(_a)
        return tf.concat(feats, axis=3)
    
    with tf.variable_scope('Gstu', reuse=tf.AUTO_REUSE):
        zs_     = [zs[-1]]
        state   = _concat(zs[-1], None, _a)
        for i in range(n_layers): # n_layers <= 4
            d   = min(dim * 2**(n_layers - 1 - i), MAX_DIM)
            output = ConvGRUCell(zs[n_layers - 1 - i], state, d, is_training=is_training,
                                 kernel_size=kernel_size, norm=norm, pass_state=pass_state)
            zs_.insert(0, output[0])
            if inject_layers > i:
                state = _concat(output[1], None, _a)
            else:
                state = output[1]
        return zs_