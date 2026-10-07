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
RAM_lo = Base_Backend + Keys_RAM + Keygen_Transient + Inputs_RAM
        + Plaintexts_RAM + Intermediates_RAM
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
Pour SEAL, le calcul ajoute une clé Galois supplémentaire comme terme transitoire pendant la génération. C'est un seul objet clé en vol, pas une modélisation de la politique TenSEAL qui génère son jeu Galois par défaut complet.

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

Les programmes communs aux deux backends sont exécutés séparément dans TenSEAL/SEAL et Lattigo avec les paramètres `(N, L)` et les tailles définis dans le script :

1. **Addition de ciphertexts** : chiffrement de plusieurs entrées, puis additions successives.
2. **Multiplications indépendantes** : chiffrement de paires d'entrées et une multiplication ciphertext-ciphertext par paire, sans empiler les niveaux.
3. **Dot product empaqueté** : multiplication de deux vecteurs chiffrés, puis réductions par rotations de puissances de deux et additions.

Les variantes communes sont 4, 16, 64 et 128 entrées pour l'addition; 2, 8, 16 et 32 produits indépendants; et des dot products empaquetés de 4 et 8 lanes. Multiplication inclut relinearisation et rescale dans les deux workers. Les dot products de 16 à 256 lanes sont réservés à Lattigo.

Trois charges sont réservées à Lattigo, qui expose les opérations correspondantes de manière fiable dans ces configurations :
- **Deep Polynomial** : trois multiplications ciphertext-ciphertext avec relinearisation et rescale en chaîne.
- **Conv2D** : convolution 3×3 sur une entrée chiffrée aplatie, avec huit rotations non nulles, multiplication par poids plaintext et additions. Ce cas n'est pas comparé à SEAL : le précédent worker SEAL n'effectuait pas le même calcul.
- **High-Churn Arithmetic** : une multiplication ciphertext-ciphertext suivie de 128 additions, pour stresser les allocations avec peu de clés.

Deep Poly n'est pas attribué à SEAL : les essais TenSEAL antérieurs échouaient par dépassement de scale. TenSEAL ne permet pas de choisir un sous-ensemble de clés Galois pour la réduction : son worker génère son jeu par défaut, plus large que les étapes du code CHEHAB; cette différence reste visible et interdit d'interpréter le dot product comme une comparaison exacte de taille de clés.

Chaque worker mesure quatre points dans des processus isolés : baseline de démarrage, pic après génération/setup des clés, pic après préparation des inputs, et pic après évaluation. Les pics sont lus avec `/usr/bin/time -v` autour de chaque processus, pas avec le high-water mark du processus parent. Pour Lattigo, la baseline suit l'initialisation des paramètres; pour TenSEAL, elle suit les imports Python et précède la création du contexte, car TenSEAL encapsule l'initialisation des clés dans son constructeur de contexte. La colonne `Actual (MB)` vaut le pic d'évaluation moins la baseline. Les colonnes `Est Delta Lo/Hi` retirent la composante `base_bytes_overhead` de l'estimateur pour comparer des incréments aux incréments. Les pics bruts des phases restent présents dans le CSV. Tous les processus Lattigo utilisent `GOGC=100`; échecs et timeouts sont notés `FAIL`, jamais comme une mesure nulle. Une hausse nulle du high-water mark est rapportée comme incrément nul, distinct d'un échec.

Le fichier `RL/sweep_results_isolated.csv` est le résultat du dernier sweep complet. Les colonnes Delta sont spécifiques à chaque backend; ne pas comparer Conv2D/Deep Poly/High-Churn à un faux résultat SEAL ni présenter les workloads différents comme une comparaison un-à-un.

Les variantes dot product de largeur 16 à 256 sont `N/A` côté SEAL par choix de comparabilité, pas parce que SEAL ne peut pas les exécuter. Une exécution TenSEAL vérifiée à `N=16384`, largeur 16, réussit, mais la phase de clés atteint 467.66 MiB (baseline 31.35 MiB) et l'évaluation 477.28 MiB. Le binding TenSEAL utilisé ici n'accepte pas une liste de pas Galois dans `generate_galois_keys`; il génère le jeu par défaut complet, contrairement au sous-ensemble de rotations CHEHAB. Ces mesures ne sont donc pas une comparaison valide du coût du jeu de clés attendu par l'estimateur. Le worker garde ces variantes Lattigo-only jusqu'à ce qu'une voie SEAL à clés sélectionnées soit disponible.

Sur le sweep relancé après actualisation de l'estimateur, la couverture de `[Est Delta Lo, Est Delta Hi]` est **0/10 pour SEAL** et **15/18 pour Lattigo**. L'erreur signée moyenne de `lo` est respectivement **-60.23 %** sur les 10 incréments RSS SEAL et **-35.43 %** sur les 18 incréments Lattigo. La corrélation de rang de Spearman vaut **0.964** pour SEAL et **0.930** pour Lattigo. Les deux dot products SEAL ont des incréments élevés dus à la génération des clés Galois. Trois mesures Lattigo restent hors intervalle : multiplication indépendante 2, Deep Polynomial et High-Churn. Aucun de ces chiffres n'est une garantie ni un résultat hold-out.

### Contrôle de programmes CHEHAB compilés

Les programmes proviennent de `benchmarks/dot_product/dot_product.cpp`, compilé par CHEHAB en source Go Lattigo, puis compilé par Go et exécuté. La campagne est reproductible avec `python3 RL/validate_compiled_programs.py` après construction de `build/benchmarks/dot_product/dot_product`. L'argument `vectorize_code=0` sélectionne la voie scalaire du benchmark; la validation porte donc sur des programmes réellement générés/exécutés, mais ne valide pas encore la voie vectorisée consommée par le mode mémoire de l'agent RL. Le script reconstruit l'AST depuis les opérations et affectations générées par le compilateur, extrait `(N,L)` du Go généré et estime ce DAG, plutôt qu'un AST synthétique ou une approximation indépendante du programme.

Chaque binaire Go a été compilé puis exécuté avec `GOGC=100`; `/usr/bin/time` mesure son RSS maximal. `lo` et `hi` sont comparés au RSS absolu du programme, baseline du processus incluse, et l'erreur signée est `(lo - RSS) / RSS * 100`. Les résultats bruts sont dans `RL/compiled_program_results.csv`.

| Largeur | N | L | Estimation lo (MiB) | Estimation hi (MiB) | RSS mesuré (MiB) | Erreur signée lo | Dans l'intervalle |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 2  | 16384 | 6 | 17.51 | 22.56 | 41.60 | -57.91 % | non |
| 4  | 16384 | 6 | 21.51 | 31.36 | 53.73 | -59.96 % | non |
| 8  | 16384 | 6 | 29.51 | 48.96 | 70.95 | -58.40 % | non |
| 16 | 16384 | 6 | 45.51 | 84.16 | 99.15 | -54.10 % | non |
| 32 | 16384 | 6 | 77.51 | 154.56 | 159.84 | -51.51 % | non |

Couverture observée : **0/5**. L'erreur signée moyenne de `lo` est **-56.38 %**; Spearman entre RSS mesuré et `lo` est **1.000** (n=5). Le classement est monotone, mais la sous-estimation absolue est importante et `hi` ne couvre aucun programme. Ces mesures n'ont pas été utilisées pour ajuster la marge. Les exécutions RSS peuvent varier d'un lancement à l'autre; les valeurs de ce tableau sont une mesure unique par largeur, pas un résultat hold-out ni une borne physique.

La voie `vectorize_code=1` a aussi été essayée, mais ne produit pas de programme dans cet environnement : le sous-processus RL échoue avant la vectorisation parce que `stable_baselines3` n'est pas installé (`ModuleNotFoundError`). Aucun résultat vectorisé n'est inclus ni extrapolé à partir des cinq programmes scalaires ci-dessus. Pour valider directement les candidats mémoire du RL, il faut d'abord restaurer cette dépendance et relancer la campagne sur des sorties vectorisées.

Le mode mémoire de l'environnement RL utilise comme paramètres fixes `N=16384`, `L=6`, cohérents avec ces programmes générés. Les autres paramètres ne sont pas automatiquement déduits pendant un épisode; il faut les fixer explicitement pour toute nouvelle campagne.

### Diagnostic High-Churn

Le workload High-Churn (N=8192, L=4, 128 additions après une multiplication) produit un DAG de 133 nœuds avec 129 opérations allouantes. Trace du live set : les quatre premières entrées/conteneurs gardent zéro intermédiaire; `VecMul` (étape 4) fait passer le live set à 1; chacune des 128 opérations `VecAdd` (étapes 5 à 132) atteint temporairement 2 puis libère l'ancien résultat, laissant 1 ciphertext vivant. Le ciphertext réutilisé comme opérande est une entrée, pas un intermédiaire. Avec `GOGC=100`, le modèle donne `slots_fixed=2`, `lo=7.51 MiB`, `hi=12.22 MiB` (deltas de 2.25/6.96 MiB après retrait de la base). Le sweep reconstruit du binaire Go donne baseline 10.36 MiB, clés 11.73 MiB, entrées 12.98 MiB et évaluation 32.23 MiB : l'incrément de 21.88 MiB dépasse le delta `hi` de 14.92 MiB. Une autre mesure isolée a produit un incrément de 12.57 MiB; cette variabilité souligne que l'intervalle ne borne pas le RSS, même avec `GOGC=100`.

Le modèle explique le pic logique, mais pas les buffers temporaires internes, l'allocateur Go ni les pages conservées à la suite des 129 allocations. Le run `GODEBUG=gctrace=1` confirme que le tas Go redescend après GC tandis que le RSS high-water mark reste supérieur. Ce cas est documenté comme une limite non résolue; la marge n'est pas augmentée sur le sweep qui sert à rapporter les résultats.

---

## 4. Limites et interprétation

- L'estimateur modélise la taille des objets selon `(N, L)`, le jeu de clés et le pic de durée de vie logique; l'usage RSS réel comprend les frais des runtimes et les temporaires internes.
- La sortie `[lo, hi]` est un intervalle du modèle, pas une garantie que chaque mesure RSS sera encadrée.
- La baseline SEAL comprend l'interpréteur Python et les imports, avant création du contexte; celle de Lattigo comprend le runtime Go et les paramètres. Les mesures d'incrément réduisent cet effet, mais les pics de phases sont des processus distincts et ne décrivent pas les temporaires internes exacts d'une seule exécution.
- `hi`/`estimated_bytes_hi` est une estimation avec marge, pas une borne supérieure physique. Les échecs de couverture doivent rester visibles et ne doivent pas être maquillés par un ajustement sur les mêmes points de test.
- Les résultats communs permettent une comparaison backend à backend. Les charges réservées à Lattigo servent uniquement à étendre la couverture des opérations.
- L'intégration RL n'estime que les AST complètement vectorisés. Les expressions scalaires ou partielles sont explicitement non estimables : elles ne sont pas filtrées par le masque mémoire et reçoivent une pénalité si l'épisode se termine sans estimation valide. L'observation conserve la dernière estimation valide, accompagnée d'un indicateur d'estimabilité.

---

## 5. Corrections et couverture des tests

Les tests de non-régression couvrent l'ordre DFS (dont un arbre où l'ordre change le pic), la comparaison à une référence récursive sur 400 arbres, une chaîne de 5 000 opérations, la conservation de tous les éléments `Vec` et des noms d'entrées par lane, la réduction des clés de rotation et la cohérence des clés estimées pour les workloads actuels.

Les conteneurs `Vec` sont conservés structurellement : aucun élément n'est supprimé et les noms de variables spécifiques aux lanes ne sont pas fusionnés. `Vec` lui-même n'est pas compté comme une opération qui alloue un ciphertext supplémentaire.

La génération du sweep a un timeout configurable (`--timeout-seconds`, 720 secondes par défaut), écrit les colonnes basse/haute et marque explicitement les exécutions échouées.