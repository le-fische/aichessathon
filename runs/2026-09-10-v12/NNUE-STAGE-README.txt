Drop weights.npy, biases.npy, weights2.npy into build/nnue-stage/weights/ then:

    cd build/nnue-stage && CHESSATHON_REQUIRE_NUMBA=1 python tools/nnue_calibrate.py

Expected shapes (from nsearch_nnue.nnue_eval and nnue_full_refresh):
    weights   (768, 256) int16
    biases    (256,)     int16
    weights2  (512,)     -- 256 side-to-move + 256 opponent (DUAL perspective)

karpov.npz cannot substitute: its fc2_w is (1, 256), a SINGLE-perspective output layer,
so it supplies half the weights nnue_eval indexes. Layer 1 would fit (fc1_w.T is
(768,256), fc1_b is (256,)); layer 2 does not.
