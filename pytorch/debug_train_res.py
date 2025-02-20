import torch
import numpy as np
from p2m.api import GCN
from p2m.utils import *
from p2m.fetcher import *
from p2m.models import Trainer
import argparse
from datetime import datetime
import os

# Set random seed
seed = 1024
np.random.seed(seed)
torch.manual_seed(seed)
use_cuda = torch.cuda.is_available()

# Settings
args = argparse.ArgumentParser()

args.add_argument('--training_data',
                  help='Training data.',
                  type=str,
                  default='data/training_data/train_list.txt')
args.add_argument('--testing_data',
                  help='Testing data.',
                  type=str,
                  default='data/testing_data/test_list.txt')
args.add_argument('--learning_rate',
                  help='Learning rate.',
                  type=float,
                  default=5e-4)
args.add_argument('--show_every',
                  help='Frequency of displaying loss',
                  type=int,
                  default=3)
args.add_argument('--weight_decay',
                  help='Weight decay for L2 loss.',
                  type=float,
                  default=5e-6)
args.add_argument('--epochs',
                  help='Number of epochs to train.',
                  type=int,
                  default=5)
args.add_argument('--cnn_type',
                  help='Type of Neural Network',
                  type=str,
                  default='RES')
args.add_argument(
    '--checkpoint',
    help='Checkpoint to use.',
    type=str,
    default='data/checkpoints/tf_res_from_vgg.pt')  # rechanged #changed
args.add_argument('--info_ellipsoid',
                  help='Initial Ellipsoid info',
                  type=str,
                  default='data/ellipsoid/info_ellipsoid.dat')
args.add_argument('--hidden',
                  help='Number of units in  hidden layer.',
                  type=int,
                  default=256)
args.add_argument('--feat_dim',
                  help='Number of units in perceptual feature layer.',
                  type=int,
                  default=963)
args.add_argument('--coord_dim',
                  help='Number of units in output layer.',
                  type=int,
                  default=3)

FLAGS = args.parse_args()

mydir = os.path.join(os.getcwd(), 'temp', FLAGS.cnn_type,
                     datetime.now().strftime('%m-%d_%H-%M-%S'))
os.makedirs(mydir)
print('---- Folder created : {}'.format(mydir))

data = DataFetcher(FLAGS.training_data)
data.setDaemon(True)
data.start()
train_number = data.number
print('---- Loadind training data, {} num samples'.format(train_number))

test_list = []
with open(FLAGS.testing_data, 'r+', encoding="utf-8") as f:
    while (True):
        line = f.readline().strip()
        if not line:
            break
        id = line.split('/')[-1][:-4]
        test_list.append((id, load_image(line)))
print('---- Loadind testing data, {} num samples'.format(len(test_list)))

tensor_dict = construct_ellipsoid_info(FLAGS)
print('---- Build initial ellispoid info')

model = GCN(tensor_dict, FLAGS)
if use_cuda:
    model.cuda()
print('---- Model Created')

model.load_state_dict(torch.load(FLAGS.checkpoint))
print('---- Model initialized from VGG')

trainer = Trainer(tensor_dict, model, FLAGS)
print('---- Trainer Created')

print('---- Training ...')
print('\n')
starter = datetime.now()
for epoch in range(FLAGS.epochs):
    start_epoch = datetime.now()
    timer = start_epoch
    epoch_dir = mydir + '/epoch_{}'.format(epoch + 1)
    os.makedirs(epoch_dir)
    os.makedirs(epoch_dir + '/outputs')
    print('-------- Folder created : {}'.format(epoch_dir))
    all_loss = np.zeros(train_number, dtype='float32')
    print('-------- Training epoch {} ...'.format(epoch + 1))
    if False:
        for iters in range(train_number):
            img_inp, y_train, data_id = data.fetch()
            img_inp, y_train = process_input(img_inp, y_train)
            if use_cuda:
                img_inp, y_train = img_inp.cuda(), y_train.cuda()
            dists, out1, out2, out3 = trainer.optimizer_step(img_inp, y_train)
            all_loss[iters] = dists
            mean_loss = np.mean(all_loss[np.where(all_loss)])
            if (iters + 1) % (50 * FLAGS.show_every) == 0:
                ckp_dir = epoch_dir + '/{}_checkpoint.pt'.format(iters + 1)
                torch.save(model.state_dict(), ckp_dir)
                print('-------- Training checkpoint {} saved !'.format(iters +
                                                                       1))
    else:
        img_inp, y_train = [], []
        for _ in range(train_number):
            sample = data.fetch()
            sample = process_input(sample[0], sample[1])
            img_inp.append(sample[0])
            y_train.append(sample[1])
        img_inp = torch.stack(img_inp)
        y_train = torch.stack(y_train)
        dists, out1, out2, out3 = trainer.optimizer_step(img_inp, y_train)
    print('-------- Training epoch {} done !'.format(epoch + 1))
    print('-------- Testing epoch {} ...'.format(epoch + 1))
    for id, img_test in test_list:
        output3 = model(img_test)[-1]
        mesh = process_output(output3)
        pred_path = epoch_dir + '/outputs/' + id + '.obj'
        np.savetxt(pred_path, mesh, fmt='%s', delimiter=' ')
    print('-------- Testing epoch {} done !'.format(epoch + 1))
    print('\n')
