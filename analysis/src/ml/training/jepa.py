"""
JEPA Self-Supervised Pre-Training

Joint Embedding Predictive Architecture for learning market structure
representations from unlabeled OHLCV sequences using InfoNCE contrastive loss.

Directly transfers the CS2 JEPA pattern (AI_BIOPSY.md §6.4):
    - Online encoder → projection → predictor
    - Target encoder (EMA-updated copy of online)
    - InfoNCE loss with temperature scaling
    - Selective decoding (skip already-well-represented states)

After pre-training, the Perception layer weights are frozen and the
Memory+Strategy+Decision layers are fine-tuned on labeled triple-barrier data.
"""

import copy
import torch
import torch.nn as nn
import torch.nn.functional as F


class JEPAPreTrainer(nn.Module):
    """
    Self-supervised pre-trainer using InfoNCE contrastive loss.

    Takes adjacent market windows as positive pairs. Learns to predict
    the target embedding of window t+1 from the online embedding of window t.
    """

    def __init__(self, encoder: nn.Module, d_input: int, d_model: int = 256,
                 tau: float = 0.996, temperature: float = 0.07):
        """
        Args:
            encoder: Perception layer (or any encoder) to pre-train.
            d_input: Output dimension of the encoder.
            d_model: Hidden/projection dimension.
            tau: EMA momentum for target encoder update.
            temperature: InfoNCE temperature.
        """
        super().__init__()
        self.tau = tau
        self.temperature = temperature

        # Online encoder + projection
        self.online_encoder = encoder
        self.online_projection = nn.Sequential(
            nn.Linear(d_input, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(512, d_model),
            nn.LayerNorm(d_model),
        )

        # Target encoder (deep copy, no gradients)
        self.target_encoder = copy.deepcopy(encoder)
        self.target_projection = copy.deepcopy(self.online_projection)
        for p in self.target_encoder.parameters():
            p.requires_grad = False
        for p in self.target_projection.parameters():
            p.requires_grad = False

        # Predictor (online only — asymmetry prevents collapse)
        self.predictor = nn.Sequential(
            nn.Linear(d_model, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(512, d_model),
        )

        # Selective decode threshold
        self.skip_threshold = 0.05

    @torch.no_grad()
    def update_target(self):
        """EMA update of target encoder and projection."""
        for online, target in [
            (self.online_encoder, self.target_encoder),
            (self.online_projection, self.target_projection),
        ]:
            for op, tp in zip(online.parameters(), target.parameters()):
                tp.data.mul_(self.tau).add_(op.data, alpha=1.0 - self.tau)

    def info_nce_loss(self, online_proj: torch.Tensor,
                      target_proj: torch.Tensor) -> torch.Tensor:
        """
        Compute InfoNCE contrastive loss.

        Args:
            online_proj: (batch, d_model) — predicted embeddings
            target_proj: (batch, d_model) — target embeddings
        Returns:
            Scalar loss.
        """
        online_norm = F.normalize(online_proj, dim=-1)
        target_norm = F.normalize(target_proj, dim=-1)

        # Similarity matrix: (batch, batch)
        sim = online_norm @ target_norm.T / self.temperature

        # Positive pairs are on the diagonal
        labels = torch.arange(sim.size(0), device=sim.device)
        return F.cross_entropy(sim, labels)

    def selective_decode(self, online_repr: torch.Tensor,
                         target_repr: torch.Tensor) -> bool:
        """
        Check if the state is already well-represented (skip if so).

        Returns:
            True if processing should be SKIPPED (states are already similar).
        """
        cosine_dist = 1.0 - F.cosine_similarity(online_repr, target_repr, dim=-1).mean()
        return cosine_dist.item() < self.skip_threshold

    def encode_online(self, x: torch.Tensor) -> torch.Tensor:
        """Run online encoder and take last timestep."""
        encoded = self.online_encoder(x)  # (batch, seq, d_input)
        last = encoded[:, -1, :]          # (batch, d_input)
        return self.online_projection(last)

    @torch.no_grad()
    def encode_target(self, x: torch.Tensor) -> torch.Tensor:
        """Run target encoder and take last timestep."""
        encoded = self.target_encoder(x)
        last = encoded[:, -1, :]
        return self.target_projection(last)

    def pretrain_step(self, x_t: torch.Tensor,
                      x_t1: torch.Tensor) -> torch.Tensor:
        """
        One pre-training step on adjacent window pair.

        Args:
            x_t:  (batch, seq, features) — window at time t
            x_t1: (batch, seq, features) — window at time t+1
        Returns:
            Scalar loss (0.0 if selective decode skips).
        """
        # Online: encode + predict
        online_repr = self.encode_online(x_t)
        predicted = self.predictor(online_repr)

        # Target: encode (no gradients)
        target_repr = self.encode_target(x_t1)

        # Selective decode: skip if already well-represented
        if self.selective_decode(online_repr.detach(), target_repr):
            return torch.tensor(0.0, device=x_t.device, requires_grad=True)

        # Loss
        loss = self.info_nce_loss(predicted, target_repr)

        # EMA update of target network
        self.update_target()

        return loss
