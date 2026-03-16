import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

def compute_pca(csv_file):

    df = pd.read_csv(csv_file, sep=None, engine="python", index_col=0)

    # keep numeric columns
    df_numeric = df.select_dtypes(include="number")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_numeric)

    pca = PCA()
    components = pca.fit_transform(X_scaled)

    explained_variance = pca.explained_variance_ratio_

    return {
        "components": components[:, :2].tolist(),
        "variance": explained_variance.tolist()
    }