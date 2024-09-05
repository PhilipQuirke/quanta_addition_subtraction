import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import IterableDataset, DataLoader, TensorDataset
import transformer_lens.utils as utils
import itertools
from sklearn.model_selection import ParameterGrid
import numpy as np

from QuantaTools.model_sae import AdaptiveSparseAutoencoder, save_sae_to_huggingface


def train_sae_epoch(sae, activation_generator, epoch, learning_rate, max_grad_norm=1.0):
    optimizer = optim.Adam(sae.parameters(), lr=learning_rate)
    scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2, verbose=True)
  
    total_loss = 0
    total_sparsity = 0    
    num_batches = 0
    
    for activations in activation_generator:
        x = activations.cuda()
        x.requires_grad_(True)
        
        optimizer.zero_grad()
        encoded, decoded = sae(x)
        loss = sae.loss(x, encoded, decoded)
        
        if torch.isfinite(loss):
            loss.backward()
            
            # Gradient clipping
            #torch.nn.utils.clip_grad_norm_(sae.parameters(), max_grad_norm)
            torch.nn.utils.clip_grad_norm_(sae.parameters(), max_norm=1.0)
            
            optimizer.step()

            total_loss += loss.item()
            total_sparsity += (encoded == 0).float().mean().item()        
            num_batches += 1
        else:
            print(f"Skipping batch due to non-finite loss: {loss.item()}")
    
    if num_batches > 0:
        avg_loss = total_loss / num_batches
        avg_sparsity = total_sparsity / num_batches
        print(f"Epoch: {epoch+1}, Avg Loss: {avg_loss:.4f}, Avg Sparsity: {avg_sparsity:.2%}")
    else:
        print(f"Epoch: {epoch+1}, No valid batches processed")
        avg_loss = float('inf')
        avg_sparsity = 0
    
    return avg_loss, avg_sparsity


def analyze_mlp_with_sae(
        cfg, 
        dataloader, 
        layer_num=0, 
        encoding_dim=512, 
        num_epochs=10, 
        learning_rate=1e-3, 
        sparsity_target=0.05, 
        sparsity_weight=1e-3, 
        early_stopping_threshold=1e-4, 
        patience=2, 
        save_directory=None):
    
    def generate_mlp_activations(main_model, dataloader, layer_num):
        hook_name = utils.get_act_name('post', layer_num)
        activations = [] 

        def store_activations_hook(act, hook):
            if len(act.shape) == 3:
                act = act.reshape(-1, act.shape[-1])
            activations.append(act.detach().cpu())
    
        try:
            main_model.add_hook(hook_name, store_activations_hook)
            for batch in dataloader:          
                _ = main_model(batch)
                yield torch.cat(activations, dim=0)
                activations = []                                
        finally:
            main_model.reset_hooks()

    activation_generator = generate_mlp_activations(cfg.main_model, dataloader, layer_num)
    sample_batch = next(activation_generator)
    input_dim = sample_batch.shape[-1]
    print("Input Dim", input_dim, "Encoding Dim", encoding_dim)

    sae = AdaptiveSparseAutoencoder(encoding_dim, input_dim, sparsity_target, sparsity_weight).cuda()

    prev_avg_loss = float('inf')
    prev_avg_sparsity = 0
    best_avg_loss = float('inf')
    best_avg_sparsity = 0
    no_improvement_count = 0

    for epoch in range(num_epochs):
        activation_generator = generate_mlp_activations(cfg.main_model, dataloader, layer_num)
        avg_loss, avg_sparsity = train_sae_epoch(sae, activation_generator, epoch, learning_rate)
        
        if torch.isfinite(torch.tensor(avg_loss)):
            loss_change = abs(avg_loss - prev_avg_loss)
            sparsity_change = abs(avg_sparsity - prev_avg_sparsity)
            
            if loss_change < early_stopping_threshold and sparsity_change < early_stopping_threshold:
                no_improvement_count += 1
                if no_improvement_count >= patience:
                    print(f"Early stopping at epoch {epoch+1} due to no significant improvement.")
                    break
            else:
                no_improvement_count = 0
            
            if avg_loss < best_avg_loss:
                best_avg_loss = avg_loss
                best_avg_sparsity = avg_sparsity
            
            prev_avg_loss = avg_loss
            prev_avg_sparsity = avg_sparsity
        else:
            print(f"Skipping epoch {epoch+1} due to non-finite loss.")
    

    if save_directory is not None:
        save_sae_to_huggingface(sae, save_directory)
        
    return sae, best_avg_loss, best_avg_sparsity


def optimize_sae_hyperparameters(cfg, dataloader, layer_num=0, num_epochs=10):
    # Define the hyperparameter grid
    param_grid = {
        'encoding_dim': [64, 128, 256, 512],
        'learning_rate': [1e-4, 1e-3, 1e-2],
        'sparsity_target': [0.01, 0.05, 0.1],
        'sparsity_weight': [1e-4, 1e-3, 1e-2]
    }

    # Generate all combinations of hyperparameters
    grid = ParameterGrid(param_grid)

    best_score = float('inf')
    best_params = None
    best_sae = None

    for params in grid:
        print(f"Testing parameters: {params}")
        sae, avg_loss, avg_sparsity = analyze_mlp_with_sae(
            cfg, 
            dataloader, 
            layer_num=layer_num, 
            encoding_dim=params['encoding_dim'],
            num_epochs=num_epochs,
            learning_rate=params['learning_rate'],
            sparsity_target=params['sparsity_target'],
            sparsity_weight=params['sparsity_weight']
        )

        # Calculate a score that balances loss and sparsity
        # You can adjust the weights of loss and sparsity in this score calculation
        if torch.isfinite(torch.tensor(avg_loss)):
            score = avg_loss - np.log(avg_sparsity)  # Example scoring function
        else:
            score = float('inf')

        if score < best_score:
            best_score = score
            best_params = params
            best_sae = sae
            print(f"Interim best parameters: {best_params}")
            print(f"Interim best score: {best_score}")
    
    print(f"Final best parameters: {best_params}")
    print(f"Final best score: {best_score}")

    return best_sae, best_params, best_score
