import torch
import torch.optim as optim
import torch.backends.cudnn as cudnn
from torch import nn
from model.ResnetBase import ResnetBase
from model.ResnetRSC import ResnetRSC
from dataset.transform import transform
from dataset.OfficeHome import OfficeHomeDataset
from evaluation import evaluate
from time import time

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

data_dir = "/kaggle/input/officehome/OfficeHomeDataset_10072016"
num_classes = 65
train_domains = ["Clipart", "Product", "Real World"]
test_domain = ["Art"]
train_loss = "train_loss.txt"
eval_metrics = "eval.txt"

checkpoint = None
batch_size = 32
lr = 0.001
iterations = 50000

cudnn.benchmark = True

# train_dataset = OfficeHomeDataset(root_dir=data_dir, domains=train_domains, transform=transform)
# train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=32, shuffle=True)
#model = ResnetBase(num_classes=65, is_nonlinear = False)
# model = ResnetRSC(num_classes=65, is_nonlinear = False, rsc_f_drop_factor = 0.33, rsc_b_drop_factor = 0.33).to(device)
# model.set_optimizer(optim.Adam(model.parameters(), lr=0.001))
# model.set_loss_fn(nn.CrossEntropyLoss())
# model.set_scheduler(optim.lr_scheduler.StepLR(model.optimizer, step_size=5, gamma=0.1))
# for epoch in range(10):
#     for x, y in train_loader:
#         x, y = x.to(device), y.to(device)
#         loss = model.update(x, y)
#     model.update_lr()
#     print(f"Epoch {epoch+1}, Loss: {loss}")
    
def save_checkpoint(epoch, model, optimizer):
    state = {'epoch': epoch,
             'model': model,
             'optimizer': optimizer}
    filename = f"checkpoint_{epoch}_test_on_{test_domain[0]}.pth.tar"
    torch.save(state, filename)
    
def train(model, train_loader, epoch):
    model.train()
    losses = []
    
    start = time()
    
    for image, label in train_loader:
        image, label = image.to(device), label.to(device)
        loss = model.update(image, label)
        losses.append(loss)
    model.update_lr()
    
    end = time()
    
    avg_loss = sum(losses) / len(losses)
    
    print(f"Epoch {epoch+1}, Training Loss: {avg_loss}, Time: {end-start}")
    del image, label, losses
    return avg_loss
    

def main():
    global start_epoch, checkpoint, epoch
    
    #Initialize the model or load checkpoint
    if checkpoint is None:
        start_epoch = 0
        model = ResnetRSC(num_classes=num_classes, is_nonlinear = False, rsc_f_drop_factor = 0.33, rsc_b_drop_factor = 0.33)
        model.set_optimizer(optim.Adam(model.parameters(), lr=lr))
        model.set_loss_fn(nn.CrossEntropyLoss())
        model.set_scheduler(optim.lr_scheduler.StepLR(model.optimizer, step_size=5, gamma=0.1))
        save_checkpoint(start_epoch, model, model.optimizer)
    
    else:
        checkpoint = torch.load(checkpoint)
        start_epoch = checkpoint['epoch'] + 1
        model = checkpoint['model']
        model.set_optimizer(checkpoint['optimizer'])

    model = model.to(device)
    train_dataset = OfficeHomeDataset(root_dir=data_dir, domains=train_domains, transform=transform)
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    
    test_dataset = OfficeHomeDataset(root_dir=data_dir, domains=test_domain, transform=transform)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    epochs = iterations // (len(train_dataset) // batch_size)
    
    for epoch in range(start_epoch, epochs):
        loss = train(model, train_loader, epoch)
        
        with open(train_loss, 'a') as f:
            f.write(f"{loss}")
            
        save_checkpoint(epoch, model, model.optimizer)
        
        if epoch % 10 == 0:
            accuracy, precision, recall = evaluate(epoch, test_loader, test_domain[0])
            
            with open(eval, 'a') as f:
                f.write(f"{accuracy}, {precision}, {recall}\n")
            
            
if __name__ == "__main__":
    main()
            
            
            
            

    
    
    
    