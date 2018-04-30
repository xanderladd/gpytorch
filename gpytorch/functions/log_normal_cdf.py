from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import math
from . import NormalCDF
from torch.autograd import Function
import torch


class LogNormalCDF(Function):
    def __init__(self):
        self.c = torch.Tensor([0.00048204, -0.00142906, 0.0013200243174, 0.0009461589032,
                               -0.0045563339802, 0.00556964649138, 0.00125993961762116,
                               -0.01621575378835404, 0.02629651521057465, -0.001829764677455021,
                               2 * (1 - math.pi / 3), (4 - math.pi) / 3, 1, 1])

        self.r = torch.Tensor([1.2753666447299659525, 5.019049726784267463450,
                               6.1602098531096305441, 7.409740605964741794425,
                               2.9788656263939928886])

        self.q = torch.Tensor([2.260528520767326969592, 9.3960340162350541504,
                               12.048951927855129036034, 17.081440747466004316,
                               9.608965327192787870698, 3.3690752069827527677])

    def forward(self, z):
        log_phi_z = z.new(*z.size()).zero_()

        # Three cases to handle: An entry of z is near zero, an entry of z is small, or an entry of z neither of these.
        z_near_zero = z.pow(2).lt(0.04)
        z_is_small = z.lt(-1)
        z_is_ordinary = (1 - z_near_zero).mul_(1 - z_is_small)

        # Case 1: Entries of z that are near zero
        if z_near_zero.sum() > 0:
            log_phi_first = -z.masked_select(z_near_zero).div_(math.sqrt(2 * math.pi))
            f = 0
            for c_i in self.c.tolist():
                f = log_phi_first.mul(c_i + f)

            log_phi_z.masked_scatter_(z_near_zero, f.mul_(-2).sub_(math.log(2)))

        # Case 2: Entries of z that are very small
        if z_is_small.sum() > 0:
            z_where_z_is_small = z.masked_select(z_is_small)
            numerator = z.new([0.5641895835477550741]).expand_as(z_where_z_is_small)
            denominator = z.new([1.0]).expand_as(z_where_z_is_small)

            for r_i in self.r:
                numerator = -z_where_z_is_small.mul(numerator.div(math.sqrt(2))) + r_i

            for q_i in self.q:
                denominator = -z_where_z_is_small.mul(denominator.div(math.sqrt(2))) + q_i

            e = numerator.div(denominator)
            log_phi_z.masked_scatter_(z_is_small, torch.log(e / 2) - z_where_z_is_small.pow(2).div_(2))

            self.denominator = denominator
            self.numerator = numerator

        log_phi_z.masked_scatter_(z_is_ordinary, torch.log(NormalCDF().forward(z.masked_select(z_is_ordinary))))

        self.save_for_backward(z, log_phi_z)
        return log_phi_z

    def backward(self, grad_output):
        z, log_phi_z = self.saved_tensors
        log_phi_z_grad = z.new().resize_as_(z).zero_()

        z_is_small = z.lt(-1)
        z_is_not_small = 1 - z_is_small

        if z_is_small.sum() > 0:
            log_phi_z_grad[z_is_small] = torch.abs(self.denominator.div(self.numerator)).mul(math.sqrt(2 / math.pi))

        exp = z[z_is_not_small].pow(2) \
                               .div(-2) \
                               .sub(log_phi_z[z_is_not_small]) \
                               .add(math.log(0.5))

        log_phi_z_grad[z_is_not_small] = torch.exp(exp).mul(math.sqrt(2 / math.pi))

        return log_phi_z_grad.mul(grad_output)
