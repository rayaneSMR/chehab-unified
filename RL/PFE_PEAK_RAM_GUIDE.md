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

### Protocole du corpus multi-benchmarks

Le nouveau runner `RL/validate_benchmark_corpus.py` étend cette vérification aux programmes générés par les benchmarks CHEHAB. La commande reproductible est `python3 RL/validate_benchmark_corpus.py --repeats 5`; le protocole gelé avant la mesure est dans `RL/compiled_corpus_protocol.json`. Il couvre 108 candidats prévus : les formes scalaires et vectorisées par e-graph des benchmarks réguliers aux largeurs 4, 8 et 16, avec la largeur 32 ajoutée pour dot product, Hamming et L2; Conv2D compilé nativement aux largeurs prises en charge; et les modes polynomial, convolution et linéaire de Deep Network. Une génération ou une exécution en échec reste consignée dans `RL/compiled_corpus_failures.csv` et n'est jamais comptée comme programme mesuré.

Chaque candidat est exécuté cinq fois avec `GOGC=100`. Le RSS absolu maximal de `/usr/bin/time` est résumé par médiane, minimum et maximum; chaque exécution conserve aussi les snapshots baseline, clés, inputs et évaluation (RSS, HWM et tas Go). L'AST est reconstruit depuis le Go généré par CHEHAB, tous les ciphertexts affectés à `encryptedOutputs` sont conservés sous une racine `Vec`, et `(N,L)` est lu dans ce même fichier. Quand un plaintext d'entrée est absent, le runner encode des vecteurs déterministes de `1.0` uniquement pour permettre l'exécution : cela ne préserve pas les valeurs métier du benchmark. Il réécrit aussi `eval.NegNew(x)` en `eval.MulNew(x, -1.0)` pour la compatibilité avec Lattigo installé. Les fichiers `RL/compiled_corpus_runs.csv`, `RL/compiled_corpus_summary.csv` et `RL/compiled_corpus_metrics.csv` sont mis à jour pendant la campagne afin de garder les résultats partiels en cas d'arrêt.

Le holdout est fixé par benchmark avant la mesure : chaque quatrième nom, dans l'ordre trié de la liste complète du runner, est réservé au holdout. Une exécution partielle conserve cette même attribution. Le rapport inclut couverture `[lo, hi]`, erreur absolue et biais signé de `lo`, Spearman moyen intra-benchmark, exactitude de classement paire à paire et faux positifs/négatifs aux budgets 64, 256 et 1024 MiB. Aucun paramètre de l'estimateur n'est ajusté sur le holdout. Ces RSS absolus incluent la baseline et ne doivent pas être mélangés aux deltas baseline-soustraits du sweep synthétique.

#### Point important : le corpus e-graph n'est pas l'intégration RL

**Non, l'estimateur n'utilise pas e-graph pour faire ses estimations.** Le rôle de l'estimateur est de recevoir un AST et d'en calculer le coût mémoire; le calcul est dans `RL/pytrs/peak_ram.py`. Dans l'environnement RL, `RL/fhe_rl/env.py` appelle `estimate_vectorized_peak_ram` sur l'expression candidate après une action de réécriture. L'estimateur n'appelle ni `gen_vectorized_code`, ni le backend e-graph, ni Stable-Baselines3. Cette séparation est intentionnelle : l'estimation doit pouvoir s'appliquer aux candidats de l'agent sans en choisir ou en optimiser un elle-même.

**En revanche, oui, l'e-graph a été utilisé pour générer une partie des programmes servant à évaluer l'estimateur.** Dans le runner de corpus, les lignes `Vectorization=vectorized` demandent la génération vectorisée (`vectorize_code=1`) et transmettent `optimization_method=0`; le benchmark CHEHAB définit `0` comme la voie e-graph et `1` comme la voie RL. Les lignes `Vectorization=scalar` désactivent la vectorisation. Le runner compile ensuite en Go/Lattigo ces sources produites, reconstruit l'AST depuis le Go généré, puis passe cet AST à la même fonction d'estimation. C'est donc le **programme d'évaluation** qui utilise une autre voie de génération; ce n'est pas l'algorithme de l'estimateur qui dépend d'e-graph.

Cette différence limite les conclusions : les 93 mesures du corpus vérifient l'estimation sur 74 candidats de développement et 19 candidats holdout générés en modes scalaires, compiler-native ou e-graph. Elles ne démontrent **pas** la précision sur les expressions exactes que produira l'agent RL pendant un épisode. En particulier, elles ne valident ni la distribution des candidats RL, ni leurs transformations intermédiaires, ni le taux d'acceptation/rejet du masque mémoire face au RSS de ces mêmes candidats. L'e-graph ne peut donc pas servir de substitut à la campagne RL prévue.

La voie de génération RL des benchmarks (`optimization_method=1`) n'a pas été mesurée dans cette campagne : son lancement échoue dans cet environnement avant de produire les candidats parce que `stable_baselines3` n'est pas installé (`ModuleNotFoundError`). Il faut rétablir cette dépendance et ajouter une collecte qui exporte chaque AST candidat réellement vu par l'environnement, puis le compiler/exécuter et mesurer son RSS avant de revendiquer une validation sur la voie RL. En attendant, les chiffres du corpus doivent être décrits comme une validation des estimateurs sur le sous-ensemble mesurable des programmes CHEHAB scalaires/e-graph/compiler-native, et non comme une validation de l'estimateur dans la boucle RL.

### Résultats du corpus compilé

La campagne a produit **93 programmes mesurés sur 108 prévus**, avec cinq exécutions chacun (**465 exécutions RSS**). Le seuil visé de 100 programmes complétés n'est donc pas atteint. Les 15 échecs restent dans `RL/compiled_corpus_failures.csv` : trois DCT vectorisés et trois `poly_derivative` vectorisés échouent sur des noms absents des maps; quatre variantes `max` et quatre `sort` terminent en erreur `object not defined`; `sort` scalaire largeur 4 échoue aussi au parsing sur l'opérande `c195`. Aucun échec n'a été transformé en mesure. Les paramètres générés couvrent six couples `(N,L)` : `(16384,6)`, `(16384,7)`, `(16384,8)`, `(16384,9)`, `(16384,10)` et `(32768,12)`.

Les métriques comparent la médiane RSS absolue au modèle non ajusté. Le holdout fixé avant mesure contient 19 programmes; le jeu de développement en contient 74.

| Mesure | Holdout | Développement | Critère préfixé |
|---|---:|---:|---:|
| Couverture de `[lo, hi]` | 31.6 % (6/19) | 35.1 % (26/74) | holdout ≥ 90 % — échec |
| Erreur absolue médiane de `lo` | 50.21 MiB | 39.59 MiB | rapportée, sans seuil |
| MAPE médiane de `lo` | 53.60 % | 54.95 % | holdout ≤ 20 % — échec |
| Biais signé moyen de `lo` | -55.30 % | -52.85 % | \|holdout\| ≤ 10 % — échec |
| Spearman moyen intra-benchmark | 0.958 | 0.944 | rapporté, sans seuil |
| Classement paire à paire intra-benchmark | 95.35 % (41/43) | 96.26 % (180/187) | holdout ≥ 80 % — passe |

En prenant `estimated_bytes_hi <= budget` comme décision « tient », le holdout a **4 faux positifs à 64 MiB**, contre le critère zéro; il n'en a aucun à 256 ni 1024 MiB. Le taux de faux rejets, calculé parmi les programmes dont le RSS mesuré tient réellement, est 0/5 à 64 MiB, 0/17 à 256 MiB et 1/19 (5.3 %) à 1024 MiB. Les taux de faux rejets respectent le seuil de 10 %, mais cela ne compense pas les faux positifs à 64 MiB. Le classement reste fort alors que les estimations absolues sont très sous-évaluées; **l'estimateur actuel ne doit pas être utilisé comme garantie de budget mémoire**. Aucun coefficient ni marge n'a été recalibré sur ce corpus ou son holdout.

Les RSS de phase sont disponibles par répétition et sous forme médiane/minimum/maximum dans les CSV. Ce corpus utilise le RSS absolu du programme, baseline comprise; ses résultats ne sont pas fusionnés avec le sweep synthétique baseline-soustrait.

#### Reproduire la campagne et lire les artefacts

La campagne doit être lancée depuis la racine du dépôt, sur Linux. Il faut que les exécutables CHEHAB des benchmarks soient déjà construits sous `build/benchmarks/<nom>/<nom>`, que Go et les dépendances du module Lattigo soient disponibles, et que `/usr/bin/time` soit installé. Le runner crée un répertoire temporaire par candidat sous `build/benchmarks`, copie les fichiers nécessaires, lance le générateur de données lorsqu'il existe, puis appelle le compilateur du benchmark pour produire le Go. Il construit ensuite un unique exécutable Go instrumenté par candidat et le réutilise pour les cinq répétitions.

Commande de la campagne documentée :

```bash
python3 RL/validate_benchmark_corpus.py --repeats 5
```

Options disponibles :

```text
--benchmarks <nom...>       sous-ensemble des benchmarks de la liste prise en charge
--widths <entier...>        largeurs à demander au runner
--repeats <entier>          répétitions d'exécution par candidat, doit être >= 1
--raw-output <chemin>       CSV détaillé par répétition et phase
--summary-output <chemin>   CSV consolidé par candidat
--metrics-output <chemin>   CSV de métriques développement/holdout
--failures-output <chemin>  CSV des erreurs de génération, compilation ou mesure
```

Pour la campagne de référence, les largeurs régulières sont 4, 8 et 16; les benchmarks `dot_product`, `hamming_dist` et `l2_distance` ont aussi une largeur 32. Conv2D est lancé nativement aux largeurs demandées jusqu'à 16. Deep Network utilise ses paramètres propres, indépendants de `--widths` : profondeurs polynomial 3/5/8, tailles convolution 3/4/8, tailles linéaires 2/4/8. La commande de référence prévoit donc 108 candidats et 540 exécutions (108 × 5) si tout compile et s'exécute. Les arguments de largeur ne changent pas le holdout.

Les quatre artefacts de données ont des rôles différents :

| Fichier | Granularité et contenu |
|---|---|
| [`compiled_corpus_runs.csv`](./compiled_corpus_runs.csv) | Une ligne par exécution. Inclut le RSS maximum externe (`/usr/bin/time`), puis pour chaque phase le RSS/HWM observé au snapshot, `HeapAlloc` et `HeapSys` du runtime Go. |
| [`compiled_corpus_summary.csv`](./compiled_corpus_summary.csv) | Une ligne par candidat compilé et mesuré. Contient le programme, sa forme, sa largeur, `(N,L)`, son split, `lo`, `hi`, RSS médian/minimum/maximum, erreur signée, indicateur d'intervalle, nombre de répétitions et résumé médian/minimum/maximum du RSS des phases. |
| [`compiled_corpus_metrics.csv`](./compiled_corpus_metrics.csv) | Une ligne par métrique et split; contient les mesures d'erreur, de classement et de décision budgétaire. |
| [`compiled_corpus_failures.csv`](./compiled_corpus_failures.csv) | Une ligne par candidat non mesuré avec le diagnostic du générateur, du compilateur, du parseur, du build Go ou de l'exécution. Un échec n'est jamais converti en RSS égal à zéro. |

Les sorties sont écrites de façon incrémentale après chaque candidat terminé ou échoué. Une campagne interrompue peut donc laisser des résultats partiels : vérifier `Repeat Count` et le nombre de lignes dans le CSV avant de les interpréter comme le corpus complet. Les CSV livrés ici correspondent à la campagne terminée de 93 candidats; ils ne sont pas présentés comme 108 mesures réussies.

#### Définition des mesures et des seuils

`Actual` dans cette validation est le RSS maximal absolu renvoyé par `/usr/bin/time` pour le processus compilé, en MiB; il inclut donc la baseline de Go, les paramètres, les clés, les entrées et l'évaluation. C'est une définition différente des deltas baseline-soustraits du sweep synthétique. La mémoire de phase est capturée depuis `/proc/self/status` au cours du même processus : `baseline` au début de `main`, `keys` après la génération des clés, `inputs` après la préparation des entrées et juste avant l'évaluation, puis `evaluation` après la fin du calcul. Les snapshots `VmRSS`/`VmHWM` sont des lectures ponctuelles; le pic complet du processus reste la valeur `/usr/bin/time`, et non le plus grand de ces quatre snapshots.

Le programme généré est aussi analysé par le modèle. Le parseur reconstruit les opérations depuis le Go émis par CHEHAB, extrait `LogN`, `LogQ` et `LogP` pour obtenir `(N,L)`, puis relie toutes les variables stockées dans `encryptedOutputs` sous un nœud `Vec` non allouant. Ainsi, les sorties multiples ne sont pas omises de l'AST estimé. La campagne mesure toutefois l'empreinte de l'exécutable, pas la justesse fonctionnelle du benchmark : pour permettre l'exécution lorsque le générateur ne renseigne pas un plaintext, l'instrumentation encode un vecteur rempli de `1.0`. Le remplacement de `eval.NegNew(x)` par `eval.MulNew(x, -1.0)` vise uniquement la compatibilité avec la version Lattigo disponible. Ces adaptations sont des limites du protocole et ne doivent pas être prises pour les vraies entrées métier.

Pour chaque candidat réussi, `Actual` utilisé dans le tableau de synthèse est la médiane des cinq RSS maximaux. Les indicateurs se calculent ainsi :

- **Couverture** : proportion des candidats pour lesquels `lo <= Actual <= hi`.
- **Erreur absolue médiane** : médiane de `abs(lo - Actual)` en MiB.
- **Erreur absolue en pourcentage (MAPE médiane)** : médiane de `abs((lo - Actual) / Actual) * 100`.
- **Biais signé moyen de `lo`** : moyenne de `((lo - Actual) / Actual) * 100`; une valeur négative indique une sous-estimation.
- **Spearman intra-benchmark** : corrélation de rang entre `lo` et RSS mesuré pour les candidats d'un même benchmark; le résultat reporté est la moyenne non pondérée des benchmarks ayant des rangs comparables. Il s'agit d'une moyenne par benchmark, pas d'un Spearman global mélangeant des circuits différents.
- **Exactitude paire à paire** : proportion des paires de candidats d'un même benchmark dont l'ordre relatif selon `lo` est le même que celui selon le RSS. Les paires à égalité sur l'estimation ou sur la mesure sont ignorées.

Pour un budget `B`, l'estimateur prédit qu'un programme tient si et seulement si `hi <= B`; le programme est mesuré comme tenant si son RSS médian `<= B`. Un **faux positif / false accept** est une prédiction « tient » alors que le RSS dépasse `B` (décision dangereuse). Le **taux de faux rejets / false reject rate** est le nombre de programmes mesurés comme tenant mais rejetés par `hi`, divisé par le nombre de programmes dont le RSS mesuré tient réellement. Le fichier des métriques fournit également ce dénominateur (`measured_fit_count`) et le nombre brut de faux positifs. Les critères d'acceptation ont été écrits dans le protocole avant la campagne : ils s'appliquent au holdout, et aucun paramètre de l'estimateur n'a été ajusté à partir de ces résultats.

#### Composition effective et échecs

Le holdout fixe contient `discrete_cosin_transform`, `hamming_dist`, `max` et `sobel`. Le découpage est au niveau benchmark, donc aucun candidat d'un de ces quatre benchmarks ne passe dans le développement. Les programmes effectivement mesurés sont répartis ainsi :

| Benchmark | Candidats prévus | Mesurés | Échecs | Split |
|---|---:|---:|---:|---|
| `box_blur` | 6 | 6 | 0 | développement |
| `conv2d` | 3 | 3 | 0 | développement |
| `deep_network` | 9 | 9 | 0 | développement |
| `discrete_cosin_transform` | 6 | 3 | 3 | holdout |
| `dot_product` | 8 | 8 | 0 | développement |
| `gx_kernel` | 6 | 6 | 0 | développement |
| `gy_kernel` | 6 | 6 | 0 | développement |
| `hamming_dist` | 8 | 8 | 0 | holdout |
| `l2_distance` | 8 | 8 | 0 | développement |
| `lin_reg` | 6 | 6 | 0 | développement |
| `matrix_mul` | 6 | 6 | 0 | développement |
| `max` | 6 | 2 | 4 | holdout |
| `poly_derivative` | 6 | 3 | 3 | développement |
| `poly_reg` | 6 | 6 | 0 | développement |
| `roberts_cross` | 6 | 6 | 0 | développement |
| `sobel` | 6 | 6 | 0 | holdout |
| `sort` | 6 | 1 | 5 | développement |
| **Total** | **108** | **93** | **15** | |

Les 15 échecs sont : trois formes vectorisées de DCT dont le générateur ne retrouve pas certaines entrées (`x1`/`x2`), quatre variantes `max` dont la génération Go s'arrête sur `object not defined`, trois formes vectorisées de `poly_derivative` avec une entrée `x` absente, quatre variantes `sort` avec `object not defined`, et `sort` scalaire largeur 4 dont le parseur ne reconnaît pas `c195`. Ces candidats ne figurent pas dans les dénominateurs de précision et leur exclusion rend la taille effective de l'échantillon plus faible que celle prévue.

La moyenne Spearman du holdout repose sur trois benchmarks ayant des rangs non dégénérés (`hamming_dist`, `max`, `sobel`). DCT a bien trois mesures scalaires, mais `lo` est identique sur ces trois largeurs; son rang d'estimation est donc dégénéré et son Spearman n'est pas défini. Le développement repose sur onze benchmarks comparables. L'exactitude paire à paire utilise 43 paires holdout et 187 paires de développement; les candidats échoués et les paires à égalité ne contribuent pas.

| Budget | Split | Programmes mesurés tenant | Faux positifs | Faux rejets | Taux de faux rejets |
|---:|---|---:|---:|---:|---:|
| 64 MiB | holdout | 5 | 4 | 0 | 0/5 = 0 % |
| 64 MiB | développement | 34 | 7 | 0 | 0/34 = 0 % |
| 256 MiB | holdout | 17 | 0 | 0 | 0/17 = 0 % |
| 256 MiB | développement | 63 | 0 | 4 | 4/63 = 6.3 % |
| 1024 MiB | holdout | 19 | 0 | 1 | 1/19 = 5.3 % |
| 1024 MiB | développement | 73 | 0 | 5 | 5/73 = 6.8 % |

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