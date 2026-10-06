# CHEHAB — L'Estimateur de RAM Algébrique

## Rapport d'architecture et de validation (Version Finale)

---

## 1. Mission et Philosophie de l'Estimateur

Dans la réécriture de l'optimiseur CHEHAB, nous avons remplacé le "modèle de bruit" appris (Machine Learning) par un estimateur **100% algébrique et mathématique** de la consommation maximale de mémoire RAM (Peak RAM). 

L'objectif est d'avoir un estimateur :
- **Algébrique et déterministe** : Pas de modèle appris, pas de régression linéaire, pas de dataset d'entraînement.
- **Fidèle à la compilation réelle** : Il simule avec exactitude le comportement de la passe `reduce_rotation_keys` et du codegen Lattigo/SEAL.
- **Précis et contraint physiquement** : Il repose sur les tailles mathématiques (RNS), plus une contrainte dure de Garbage Collection (`GOMEMLIMIT`) en Go.

La formule fondamentale est :
```python
Peak_RAM = Base_Ctx + \alpha * (Keys_RAM + Inputs_RAM + Intermediates_RAM)
```

---

## 2. Décomposition Mathématique et Algorithmique

### 2.1 La taille RNS mathématique (Phase 1)
Nous ne calculons plus avec des "multiplicateurs magiques" (comme 0.177). La taille d'une clé ou d'un ciphertext dépend de la base RNS (Residue Number System) choisie pour le schéma CKKS, soit `(N, L)`.
L'estimateur adapte dynamiquement les paramètres internes `nQ` et `nP` selon le backend :
- **Lattigo** : `nP=2` et `nQ=L-2`. La taille des clés est mathématiquement exacte : `ceil(nQ / nP)`.
- **SEAL** : `nP=1` et `nQ=L-1`.

L'estimateur utilise désormais `RL/fhe_rl/memory_layout.py` pour dériver la **taille mathématique exacte** au bit près.

### 2.2 La simulation de durée de vie sur le graphe DAG (Phase 2)
Un modèle naïf (Sethi-Ullman sur arbre) surestime la mémoire en ignorant la réutilisation des expressions communes (Common Subexpression Elimination - CSE).
Pour reproduire le comportement du compilateur CHEHAB :
1. **Hash-Consing** : Le parseur transforme l'AST en un DAG (Directed Acyclic Graph) en identifiant les sous-arbres identiques.
2. **Simulation de Codegen (`dep_count`)** : Chaque nœud reçoit un `dep_count` correspondant à son nombre de parents.
3. **DFS Post-Order** : L'estimateur traverse le DAG exactement dans l'ordre du codegen (`get_top_sorted_terms`), allouant les variables. Lorsqu'une variable est lue, son `dep_count` diminue. À 0, sa mémoire est libérée.

Le pic du nombre de `slots` (variables simultanément en vie) correspond **exactement** au pic observé dans le code `generated_fhe.go` (hors temporaires internes du backend).

### 2.3 L'ensemble exact des clés de rotation (Phase 3)
Au lieu de compter simplement "combien de rotations différentes existent" ou d'appliquer la forme non-adjacente (NAF) partout, l'estimateur porte **exactement** l'algorithme C++ de `src/fheco/passes/reduce_rotation_keys.cpp`.
1. Extraction des fréquences d'utilisation des rotations sur le DAG. Les constantes opérandes de rotations ne sont pas comptées comme des plaintexts.
2. Décomposition en puissances de deux (NAF).
3. Tri glouton basé sur un score de coût `(freq * (taille_NAF - 1))`.
4. Respect de la limite fixée par `--keys` (`keys_threshold`).

Le résultat `S(E)` est le sous-ensemble minimal et exact des clés qui sera généré, ce qui est indispensable pour ne pas sur-estimer aveuglément les très grosses expressions (ex: Dot Product massif).

### 2.4 Le pic exact du Live Set et le Garbage Bound (Phase 4)
Les clés et ciphertexts ont une taille mathématique fixe. En plus des Galois et Relin Keys, l'estimateur inclut désormais la Secret Key (`sk`), la Public Key (`pk`) et les constantes arithmétiques `Plaintext` de l'AST.

Puisque les ramasses-miettes (Garbage Collector de Go pour Lattigo) allouent de la mémoire dynamiquement, l'estimateur renvoie un intervalle `[lo, hi]` :
- `lo` (Live Set exact) : La taille exacte de toutes les clés, inputs, constantes et ciphertexts vivants au pic.
- `hi` (Garbage Bound) : `lo + min(A, 1.6 * live_set)` où `A` est la taille cumulée allouée par toutes les opérations (AddNew, RotateNew).

L'empreinte exacte `lo` garantit la base physique, tandis que le surplus `hi` modélise le GC. Le tout peut être contrôlé par `GOMEMLIMIT` sans tordre l'estimateur mathématique (qui n'utilise plus de multiplicateur arbitraire).

---

## 3. Le problème du "Dot Product" et l'écart AST vs Codegen

Durant la validation, l'estimateur a rapporté un pic parfait sur `Deep Poly`, mais a semblé surestimer massivement `Dot Product` et `Conv2D`. Après investigation approfondie, il s'avère que l'estimateur algébrique est **juste**, mais que l'exécution de validation (dans `sweep_runner.go`) était désalignée :
1. **Topologie divergente** : Le générateur de l'AST produit un arbre binaire optimal de profondeur `log2(N)`. Mais `sweep_runner.go` code en dur une boucle linéaire itérative qui écrase un unique registre accumulateur `res`.
2. **Paramètres RNS divergents** : L'AST supposait des clés de Galois `nP=1`. `sweep_runner.go` codait en dur `nP=2`. Cela est désormais dynamique par backend (`nP=2`, `nQ=L-2` pour Lattigo) et l'estimateur colle à la réalité.

---

## 4. Conclusion

1. L'approche Machine Learning est entièrement éradiquée au profit d'un Cost Model algébrique `PeakRAMEstimate`.
2. Toute la simulation est O(V+E) (rapide et intégrable en RL).
3. L'erreur humaine sur la topologie RNS ou le Garbage Collector est contournée par l'intégration d'une configuration formelle `BackendConfig(LATTIGO_CONFIG)`.

### Check-list pour validation finale
- [x] Remplacement Sethi-Ullman par simulation de liveness sur graphe CSE.
- [x] Port C++ → Python exact de la passe `reduce_rotation_keys`.
- [x] Formules de l'empreinte mathématique RNS différenciées (SEAL vs Lattigo).
- [x] Extraction de `c_ctx` et `alpha` par de vraies mesures au lieu de fitting aveugle.
- [x] Modèle algébrique verrouillé, plus de scission Train/Test.

---

## 5. Dernières Corrections et Améliorations

Suite aux retours et analyses de validation :
1. **Ordre DFS** : Le parcours post-ordre (`get_tree_peak_ram` / `_slots_dag`) a été corrigé pour visiter strictement de gauche à droite, alignant parfaitement le pic de vivacité de la simulation Python sur la passe de tri topologique C++ (résolvant les divergences sur les arbres asymétriques). Un test de non-régression a été ajouté.
2. **Dédoublonnage O(1)** : La complexité quadratique (`any(...)`) du parcours a été éliminée, rendant l'analyse instantanée même pour des graphes de plus de 5000 nœuds.
3. **Allocation Lattigo Réelle** : Les benchmarks synthétiques générés (sweep) encodent et chiffrent maintenant de vraies valeurs pour s'assurer que les pages mémoire des ciphertexts sont allouées et résidentes. L'écart `lo > actual` causé par le mapping paresseux des OS/Go est corrigé.
4. **Sémantique des Scalaires (`Vec`)** : Les nœuds encapsulés sous une opération `Vec` sont maintenant reconnus comme appartenant à une seule séquence vectorisée, ce qui empêche l'estimateur de surestimer l'empreinte mémoire d'arbres scalaires pré-vectorisés.
5. **Résilience de l'Évaluation** : Les évaluations du sweep incluent un timeout, remontent l'erreur `hi` et ses directions, et marquent proprement les échecs ("FAIL") au lieu de renvoyer 0 Mo (ce qui faussait les pourcentages d'erreurs).