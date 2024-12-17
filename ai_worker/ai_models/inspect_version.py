import h5py
import os

def inspect_model_version(model_path):
    with h5py.File(model_path, 'r') as f:
        print("### Attributs Racine ###")
        for key, value in f.attrs.items():
            print(f"{key}: {value}")

        print("\n### Contenu du Fichier HDF5 ###")
        def print_structure(name):
            print(name)
        f.visit(print_structure)

        # Vérifiez les attributs spécifiques si présents
        if 'keras_version' in f.attrs:
            print(f"\nKeras version: {f.attrs['keras_version']}")
        if 'tensorflow_version' in f.attrs:
            print(f"TensorFlow version: {f.attrs['tensorflow_version']}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, 'AImodel_BSC_AF class1.h5')
    inspect_model_version(model_path)