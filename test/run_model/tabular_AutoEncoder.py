import argparse
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from pytorch_lightning import Trainer, seed_everything
from pytorch_lightning.callbacks import EarlyStopping, RichProgressBar
from pytorch_lightning.callbacks.progress.rich_progress import RichProgressBarTheme
from pytorch_lightning.loggers import TensorBoardLogger
from torch.utils.data import DataLoader

from catchMinor.data_load.dataset import tabularDataset
from catchMinor.tabular_model.AutoEncoder.ae_config import (
    AutoEncoder_config,
    AutoEncoder_loss_func_config,
    AutoEncoder_optimizer_config,
)
from catchMinor.tabular_model.AutoEncoder.lit_ae import LitBaseAutoEncoder
from catchMinor.utils.data import normal_only_train_split_tabular


def define_argparser():
    parser = argparse.ArgumentParser()

    parser.add_argument("--project", default="Tabular Anomaly Detection")
    parser.add_argument("--model", default="LitBaseAutoEncoder")
    parser.add_argument(
        "--batch_size",
        type=int,
        default=512,
        help="input batch size for training (default: 512)",
    )
    parser.add_argument(
        "--epochs", type=int, default=5, help="number of epochs to train (default: 5)"
    )
    parser.add_argument("--cuda", type=int, default=0, help="0 for cpu -1 for all gpu")

    config = parser.parse_args()  # jupyter에서는 args=[] 이용

    if config.cuda == 0 or not torch.cuda.is_available():
        config.cuda = "cpu"
    else:
        config.cuda = "gpu"

    current_time = str(datetime.today()).split(".")[0]
    config.current_time = current_time

    return config


if __name__ == "__main__":
    seed_everything(42)
    config = define_argparser()
    data_path = Path(__file__).parents[2] / "data" / "tabular"

    tmp_data = os.listdir(data_path)[1]
    print(f"data = {tmp_data}")
    data_path = str(data_path) + "/" + tmp_data
    data = np.load(data_path)
    X, y = data["X"], data["y"]  # |X| = (223, 9)

    (
        normal_X_train,
        mix_X_test,
        normal_y_train,
        mix_y_test,
    ) = normal_only_train_split_tabular(X, y, 0.8)

    train_dataset = tabularDataset(normal_X_train, deepcopy(normal_X_train))
    valid_dataset = tabularDataset(mix_X_test, deepcopy(mix_X_test))

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size)
    valid_loader = DataLoader(valid_dataset, batch_size=config.batch_size)

    model_config = AutoEncoder_config(features_dim_list=[9, 4])
    optim_config = AutoEncoder_optimizer_config()
    loss_func_config = AutoEncoder_loss_func_config(loss_fn="MSELoss")

    model = LitBaseAutoEncoder(model_config, optim_config, loss_func_config)

    # trainer
    TensorBoard_logger = TensorBoardLogger(
        save_dir="./log", name=config.model, version=config.current_time
    )

    rich_progress_bar = RichProgressBar(
        theme=RichProgressBarTheme(
            description="Anomaly Detection",
            progress_bar="green1",
            progress_bar_finished="green1",
            progress_bar_pulse="#6206E0",
            batch_progress="green_yellow",
            time="grey82",
            processing_speed="grey82",
            metrics="grey82",
        ),
        leave=True,
    )

    early_stopping_callback = EarlyStopping(monitor="val_loss", mode="min", patience=2)
    trainer = Trainer(
        log_every_n_steps=1,
        accelerator=config.cuda,
        logger=TensorBoard_logger,
        max_epochs=config.epochs,
        deterministic=True,
        callbacks=[early_stopping_callback, rich_progress_bar],
        check_val_every_n_epoch=1,
    )

    # fit the model
    trainer.fit(model, train_loader, valid_loader)
