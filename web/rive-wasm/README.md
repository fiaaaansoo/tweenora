# web/rive-wasm : couche WebAssembly et JavaScript

Ce dossier est issu de [`rive-wasm`](https://github.com/rive-app/rive-wasm) (MIT, © 2020-2021 Rive), importé par `git subtree` au
commit `589b787c8a50b528db0071d9bc22e6b21ab13604`. Il est compilé contre le runtime de ce dépôt (`runtime/`) et publié sous
le nom `@tweenora/webgl2` (rendu WebGL2). Tweenora n'est ni affilié à Rive ni approuvé par Rive.

- Le texte de la licence d'origine est conservé dans [`LICENSE`](LICENSE) ; les notices des bibliothèques liées dans `rive.wasm`
  sont dans `js/npm/webgl2/THIRD_PARTY_NOTICES`.
- Les écarts par rapport à l'amont (renommage du paquet, chargement du `.wasm` sans CDN, fichiers retirés) sont consignés dans
  [`../UPSTREAM.md`](../UPSTREAM.md).
- Pour construire le paquet et lancer la démo : [`../README.md`](../README.md) ; exemples d'usage de l'API :
  [`../examples/README.md`](../examples/README.md).
- Le `CHANGELOG.md` et le `CONTRIBUTING.md` de ce dossier sont ceux de l'amont et ne décrivent pas le fonctionnement de ce
  dépôt ; pour contribuer à Tweenora, voir le [`CONTRIBUTING.md`](../../CONTRIBUTING.md) racine.
