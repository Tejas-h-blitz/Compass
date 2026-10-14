# Paper Summary: Attention Is All You Need

**Authors:** Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin.

## Core Innovation
Prior sequence transduction models relied heavily on complex recurrent neural networks (RNNs, LSTMs, GRUs) or convolutional networks. These architectures suffer from inherent sequential constraints: computations for time step t depend strictly on hidden state h_{t-1}, precluding parallelization across long context windows.

The Transformer architecture dispenses entirely with recurrence, relying solely on **Self-Attention** mechanisms to compute representations of input sequences. Scaled Dot-Product Attention computes attention weights dynamically: Attention(Q, K, V) = softmax((Q * K^T) / sqrt(d_k)) * V.

Multi-Head Attention allows the model to jointly attend to information from different representation subspaces at different positions.