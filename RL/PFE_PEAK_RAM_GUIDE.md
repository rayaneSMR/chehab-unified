# CHEHAB — L'Estimateur de RAM Algébrique

## Rapport d'architecture et de validation (état courant)

---

## 1. Mission et Philosophie de l'Estimateur

Dans la réécriture de l'optimiseur CHEHAB, nous avons remplacé le "modèle de bruit" appris (Machine Learning) par un estimateur **100% algébrique et mathématique** de la consommation maximale de mémoire RAM (Peak RAM). 

L'objectif est d'avoir un estimateur :
- **Algébrique et déterministe** : Pas de modèle appris, pas de régression linéaire, pas de dataset d'entraînement.
- **Aligné sur le compilateur** : Il suit l'ordre DFS de gauche à droite du tri topologique C++ et porte la logique de réduction des clés de rotation.
- **Interprétable** : Il sépare les clés, les entrées, les plaintexts et les ciphertexts intermédiaires, puis produit une estimation basse et une estimation haute.

Le modèle utilisé actuellement est :
```python
RAM_lo = Base_Backend + Keys_RAM + Inputs_RAM + Plaintexts_RAM + Intermediates_RAM
RAM_hi = 1.1 * (RAM_lo + Garbage_Bound)
```
Ce sont des estimations analytiques, pas une borne physique garantie. Les mesures RSS des processus servent à comparer le modèle aux exécutions.

---

## 2. Décomposition Mathématique et Algorithmique

### 2.1 La taille RNS mathématique (Phase 1)
Nous ne calculons plus avec des "multiplicateurs magiques" (comme 0.177). La taille d'une clé ou d'un ciphertext dépend de la base RNS (Residue Number System) choisie pour le schéma CKKS, soit `(N, L)`.
L'estimateur adapte dynamiquement les paramètres internes `nQ` et `nP` selon le backend :
- **Lattigo** : `nP=2` et `nQ=L-2`. La taille des clés est mathématiquement exacte : `ceil(nQ / nP)`.
- **SEAL** : `nP=1` et `nQ=L-1`.

L'estimateur utilise `RL/fhe_rl/memory_layout.py` pour calculer les tailles théoriques des objets RNS selon le backend. Ces tailles modélisées ne comprennent pas tous les détails des allocateurs ni les temporaires internes des bibliothèques.

### 2.2 La simulation de durée de vie sur le graphe DAG (Phase 2)
Un modèle naïf (Sethi-Ullman sur arbre) surestime la mémoire en ignorant la réutilisation des expressions communes (Common Subexpression Elimination - CSE).
Pour reproduire le comportement du compilateur CHEHAB :
1. **DAG** : Le parcours travaille sur les nœuds partagés de l'AST (par exemple après CSE). Il ne fusionne pas de lui-même des sous-arbres distincts qui seraient seulement structurellement égaux.
2. **Simulation de Codegen (`dep_count`)** : Chaque nœud reçoit un `dep_count` correspondant à son nombre de parents.
3. **DFS Post-Order** : L'estimateur traverse le DAG exactement dans l'ordre du codegen (`get_top_sorted_terms`), allouant les variables. Lorsqu'une variable est lue, son `dep_count` diminue. À 0, sa mémoire est libérée.

Le parcours est itératif, afin d'éviter les limites de récursion sur les expressions profondes. L'ordre des enfants est choisi pour reproduire le DFS gauche-à-droite du tri topologique dans `src/fheco/ir/expr.cpp`. Les tests le vérifient sur un arbre asymétrique, le comparent à une référence récursive sur 400 arbres déterministes et couvrent une chaîne de 5 000 opérations. Le nombre de slots décrit le modèle de durée de vie; il ne garantit pas à lui seul le RSS exact de la bibliothèque.

### 2.3 L'ensemble exact des clés de rotation (Phase 3)
Au lieu de compter simplement "combien de rotations différentes existent" ou d'appliquer la forme non-adjacente (NAF) partout, l'estimateur porte **exactement** l'algorithme C++ de `src/fheco/passes/reduce_rotation_keys.cpp`.
1. Extraction des fréquences d'utilisation des rotations sur le DAG. Les constantes opérandes de rotations ne sont pas comptées comme des plaintexts.
2. Décomposition en puissances de deux (NAF).
3. Tri glouton basé sur un score de coût `(freq * (taille_NAF - 1))`.
4. Respect de la limite fixée par `--keys` (`keys_threshold`).

Le résultat `S(E)` est le jeu de clés produit par cette passe de réduction. Les tests Python couvrent des jeux attendus, les pas sous le seuil et le cas d'un seuil impossible. Les rotations synthétiques ne font pas partie des workloads du sweep actuel.

### 2.4 Le pic modélisé du Live Set et le Garbage Bound (Phase 4)
Les clés et ciphertexts ont une taille mathématique fixe. En plus des Galois et Relin Keys, l'estimateur inclut désormais la Secret Key (`sk`), la Public Key (`pk`) et les constantes arithmétiques `Plaintext` de l'AST.

L'estimateur renvoie un intervalle `[lo, hi]` :
- `lo` (empreinte modélisée) : La somme de la base backend, des clés, des inputs, des constantes et des ciphertexts vivants au pic simulé.
- `hi` (marge de déchets) : `1.1 * (lo + min(A, 1.6 * live_set))`, où `A` est l'estimation des allocations d'opérations et `live_set` la somme modélisée des clés, inputs, plaintexts et intermédiaires.

Dans l'implémentation actuelle, `hi = 1.1 * (lo + garbage_bound)`. Le terme de déchets est utilisé pour Lattigo; il est nul pour SEAL dans ce modèle. `lo` n'est pas un RSS minimum garanti et `hi` n'est pas un RSS maximum garanti. L'empreinte observée dépend également du runtime, de l'allocateur et des temporaires de chaque backend.

---

## 3. Workloads de validation actuels

Le sweep reproductible est lancé depuis la racine du dépôt :

```bash
python3 RL/generate_sweep_isolated.py
```

Il compare trois opérations CKKS directement exécutées dans les deux workers, aux paramètres `(N, L)` et tailles d'entrée définis dans le script :

1. **Addition de ciphertexts** : chiffrement de plusieurs entrées, puis additions successives.
2. **Multiplications indépendantes** : chiffrement de paires d'entrées et une multiplication ciphertext-ciphertext par paire, sans empiler les niveaux.
3. **Dot product** : multiplications de paires suivies de l'addition des produits.

Les variantes actuelles sont 4, 16, 64 et 128 entrées pour l'addition; 2, 8, 16 et 32 produits indépendants; et des dot products de 4 à 256 entrées. Les paramètres exacts sont définis dans `RL/generate_sweep_isolated.py`. Le résultat est enregistré dans `RL/sweep_results_isolated.csv`. Chaque backend s'exécute dans un processus séparé; les erreurs et délais dépassés sont inscrits `FAIL`, jamais comme une mesure de zéro.

Les anciens cas **Deep Poly** et **Conv2D** ont été écartés :
- Les profondeurs Deep Poly testées dépassaient la capacité d'échelle TenSEAL disponible dans ces configurations CKKS.
- Les anciens workers Conv2D ne faisaient pas la même opération : le worker SEAL utilisait une approximation par multiplications matricielles denses, tandis que le worker Lattigo mesurait surtout rotations et clés de rotation. Ces valeurs n'étaient donc pas comparables.

La mesure SEAL est le `ru_maxrss` du processus Python/TenSEAL et inclut l'interpréteur ainsi que ses dépendances. La mesure Lattigo est le RSS maximal du processus Go. Les frais de runtime sont particulièrement importants pour les petits cas. Ces données comparent des exécutions de processus complets, pas uniquement la mémoire interne des bibliothèques.

---

## 4. Limites et interprétation

- L'estimateur modélise la taille des objets selon `(N, L)`, le jeu de clés et le pic de durée de vie logique; l'usage RSS réel comprend les frais des runtimes et les temporaires internes.
- La sortie `[lo, hi]` est un intervalle du modèle, pas une garantie que chaque mesure RSS sera encadrée.
- Les mesures du sweep sont des pics RSS de processus isolés. Pour SEAL/TenSEAL, l'initialisation Python est incluse; les tailles de petites charges doivent donc être interprétées avec prudence.
- Les workloads sont conçus pour les opérations prises en charge directement par les deux workers. Ne pas ajouter de convolution ou de benchmark à rotations uniquement d'un côté sans implémenter le même calcul de l'autre côté.

---

## 5. Corrections et couverture des tests

Les tests de non-régression couvrent l'ordre DFS (dont un arbre où l'ordre change le pic), la comparaison à une référence récursive sur 400 arbres, une chaîne de 5 000 opérations, la conservation de tous les éléments `Vec` et des noms d'entrées par lane, la réduction des clés de rotation et la cohérence des clés estimées pour les workloads actuels.

Les conteneurs `Vec` sont conservés structurellement : aucun élément n'est supprimé et les noms de variables spécifiques aux lanes ne sont pas fusionnés. `Vec` lui-même n'est pas compté comme une opération qui alloue un ciphertext supplémentaire.

La génération du sweep a un timeout configurable (`--timeout-seconds`, 720 secondes par défaut), écrit les colonnes basse/haute et marque explicitement les exécutions échouées.