import torch
import torch.nn as nn
from Net.base_net import *

def swish(x):
    return x * x.sigmoid()

def hard_sigmoid(x, inplace=False):
    return nn.ReLU6(inplace=inplace)(x + 3) / 6

def hard_swish(x, inplace=False):
    return x * hard_sigmoid(x, inplace)

class HardSigmoid(nn.Module):
    def __init__(self, inplace=False):
        super(HardSigmoid, self).__init__()
        self.inplace = inplace

    def forward(self, x):
        return hard_sigmoid(x, inplace=self.inplace)

class HardSwish(nn.Module):
    def __init__(self, inplace=False):
        super(HardSwish, self).__init__()
        self.inplace = inplace

    def forward(self, x):
        return hard_swish(x, inplace=self.inplace)

def _make_divisible(v, divisor=8, min_value=None): 
    """
    This function is taken from the original tf repo.
    It ensures that all layers have a channel number that is divisible by 8
    It can be seen here:
    https://github.com/tensorflow/models/blob/master/research/slim/nets/mobilenet/mobilenet.py
    :param v:
    :param divisor:
    :param min_value:
    :return:
    """
    if min_value is None:
        min_value = divisor
    new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
    # Make sure that round down does not go down by more than 10%.
    if new_v < 0.9 * v:
        new_v += divisor
    return new_v


class SELayer(nn.Module):
    def __init__(self, inp, oup, reduction=4):
        super(SELayer, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
                nn.Conv2d(oup, _make_divisible(inp // reduction), 1, 1, 0,),
                nn.ReLU(),
                nn.Conv2d(_make_divisible(inp // reduction), oup, 1, 1, 0),
                HardSigmoid()
        )

    def forward(self, x):
        b, c, _, _ = x.size()
        y = self.avg_pool(x)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y

class ConvBlock1(nn.Module):
    def __init__(self):
        super(ConvBlock1, self).__init__()
        self.DW = nn.Conv2d(in_channels=16, out_channels=16, kernel_size=3, stride=1, groups=16, padding=1, bias=False)
        self.BN = nn.BatchNorm2d(16)
        self.HS = HardSwish()
        self.PW = nn.Conv2d(in_channels=16, out_channels=32, kernel_size=1, stride=1, padding=0, bias=False)
        self.BNN = nn.BatchNorm2d(32)

    def forward(self, x):
        a = self.HS(self.BN(self.DW(x)))
        a = self.HS(self.BNN(self.PW(a)))
        return a

class ConvBlock2(nn.Module):
    def __init__(self):
        super(ConvBlock2, self).__init__()
        self.DW = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, groups=32, padding=1, bias=False)
        self.BN = nn.BatchNorm2d(32)
        self.HS = HardSwish()
        self.PW = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=1, stride=1, padding=0, bias=False)
        self.BNN = nn.BatchNorm2d(64)

    def forward(self, x):
        a = self.HS(self.BN(self.DW(x)))
        a = self.HS(self.BNN(self.PW(a)))
        return a

class ConvBlock3(nn.Module):
    def __init__(self):
        super(ConvBlock3, self).__init__()
        self.DW = nn.Conv2d(in_channels=160, out_channels=160, kernel_size=3, stride=1, groups=160, padding=1, bias=False)
        self.BN = nn.BatchNorm2d(160)
        self.HS = HardSwish()
        self.PW = nn.Conv2d(in_channels=160, out_channels=64, kernel_size=1, stride=1, padding=0, bias=False)
        self.BNN = nn.BatchNorm2d(64)

    def forward(self, x):
        a = self.HS(self.BN(self.DW(x)))
        a = self.HS(self.BNN(self.PW(a)))
        return a

class ConvBlock4(nn.Module):
    def __init__(self):
        super(ConvBlock4, self).__init__()
        self.DW = nn.Conv2d(in_channels=144, out_channels=144, kernel_size=3, stride=1, groups=144, padding=1, bias=False)
        self.BN = nn.BatchNorm2d(144)
        self.HS = HardSwish()
        self.PW = nn.Conv2d(in_channels=144, out_channels=64, kernel_size=1, stride=1, padding=0, bias=False)
        self.BNN = nn.BatchNorm2d(64)
        self.SE = SELayer(144, 144)

    def forward(self, x):

        a = self.HS(self.BN(self.DW(x)))
        a = self.SE(a)
        a = self.HS(self.BNN(self.PW(a)))
        return a

class LEDNet(nn.Module):
    def __init__(self, num_layers=3):
        super(LEDNet, self).__init__()
        self.input = nn.Conv2d(in_channels=3, out_channels=16, kernel_size=1, stride=1, padding=0, bias=False)  ## 第一层卷积
        
        self.output = nn.Conv2d(in_channels=64, out_channels=3, kernel_size=1, stride=1, padding=0, bias=False)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool_r1 = MaxPooling2D()
        self.maxpool_r2 = MaxPooling2D()
        self.deconv_r1 = ConvTranspose2D(64, 128)
        self.concat_r1 = Concat()
        self.deconv_r2 = ConvTranspose2D(64, 128)
        self.concat_r2 = Concat()
        self.out = nn.Sigmoid()

        self.block1 = ConvBlock1()
        self.block2 = ConvBlock2()
        self.block3 = ConvBlock3()
        self.block4 = ConvBlock4()

    def forward(self, x):
        # 3->16
        x = self.input(x)
        maxpool_r1 = self.maxpool_r1(x)
        # 16->32
        x1 = self.block1(maxpool_r1)

        maxpool_r2 = self.maxpool_r2(x1)
        # 32->64
        x2 = self.block2(maxpool_r2)

        # 64->128
        deconv_r1 = self.deconv_r1(x2)
        # 128->128+32=160
        concat_r1 = self.concat_r1(x1, deconv_r1)
        # 160->64
        x3 = self.block3(concat_r1)
        
        # 64->128
        deconv_r2 = self.deconv_r2(x3)
        # 128->128+16=144
        concat_r2 = self.concat_r2(x, deconv_r2)
        # 144->64
        x4 = self.block4(concat_r2)
        # 64->3
        out = self.output(x4)
        
        out = self.out(out)
        return out