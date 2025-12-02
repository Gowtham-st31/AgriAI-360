import tensorflow as tf, traceback, sys
try:
    print("Python:", sys.version.split()[0])
    print("TensorFlow:", tf.__version__)
    tf.keras.models.load_model("model.keras")
    print("MODEL_LOADED_OK")
except Exception:
    print("MODEL_LOAD_ERROR")
    traceback.print_exc()
