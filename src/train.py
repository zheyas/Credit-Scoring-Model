import torch
from sklearn.metrics import roc_auc_score

def train_model(model, train_loader, val_loader, epochs=10, lr=1e-3):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.BCELoss()

    for epoch in range(epochs):
        model.train()
        for xb, yb in train_loader:
            xb = xb.float()
            yb = yb.float().view(-1,1)
            preds = model(xb)
            loss = criterion(preds, yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Валидация
        model.eval()
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.float()
                preds = model(xb)
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(yb.cpu().numpy())

        roc_auc = roc_auc_score(all_targets, all_preds)
        print(f"Epoch {epoch+1}, ROC-AUC: {roc_auc:.4f}")
