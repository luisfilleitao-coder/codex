---
name: threejs
description: Build, debug and review 3D scenes with three.js (WebGL and WebGPU). Use when the user asks about three.js, Scene, PerspectiveCamera, WebGLRenderer, WebGPURenderer, meshes, materials, lights, loaders (GLTFLoader), OrbitControls, animation loops, or TSL shader nodes (`three/tsl`). Also use for "3D", "WebGL", "WebGPU", "cena 3D", "renderizar", "Three.js" in Portuguese or English.
---

# three.js (r187 reference)

This skill is based on the official three.js documentation for version **0.187.0** (`docs/pages/*.md` in mrdoob/three.js). Check `package.json` in the user's project before relying on version-specific behavior. The docs for other versions may differ.

## Core workflow

1. **Identify the setup.** Is it a plain HTML page, a bundler project (Vite, webpack), or a Node/SSR context? Check how `three` is imported.
2. **Pick the renderer.**
   - `WebGLRenderer`: the stable default, works everywhere.
   - `WebGPURenderer` (`three/webgpu`): newer. Falls back to WebGL 2 when WebGPU is unavailable. Must be initialized with `await renderer.init()` before the first render.
   - Do not mix the two in one scene setup. TSL node materials (`three/tsl`) need `WebGPURenderer` or the WebGPU build.
3. **Build the minimal scene graph**: `Scene` → objects (`Mesh` = geometry + material), lights, and a camera.
4. **Render through `setAnimationLoop`** rather than a hand-written `requestAnimationFrame` loop. It handles XR and works with both renderers.
5. **Verify.** Run the code, or at least check the console for errors, and confirm the canvas size and aspect ratio are correct.

## Minimal WebGL example

```js
import * as THREE from 'three';

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.z = 5;

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const mesh = new THREE.Mesh(
  new THREE.BoxGeometry(1, 1, 1),
  new THREE.MeshStandardMaterial({ color: 0x44aa88 })
);
scene.add(mesh);
scene.add(new THREE.DirectionalLight(0xffffff, 2).translateX(2).translateY(3));
scene.add(new THREE.AmbientLight(0xffffff, 0.3));

renderer.setAnimationLoop(() => {
  mesh.rotation.y += 0.01;
  renderer.render(scene, camera);
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

## Import rules

- Core: `import * as THREE from 'three'`.
- Addons (controls, loaders, postprocessing): `three/addons/...`, for example `three/addons/controls/OrbitControls.js` and `three/addons/loaders/GLTFLoader.js`. Addons are not in the core bundle.
- WebGPU: `import * as THREE from 'three/webgpu'`. TSL: `import { Fn, uniform, texture, uv, vec3, mix, time, oscSine, positionLocal, normalWorld } from 'three/tsl'`.
- Bundler-free pages need an import map. Map `"three"` to `build/three.module.js` and `"three/addons/"` to `examples/jsm/`. For WebGPU, also map `"three/webgpu"` and `"three/tsl"`.

## Constructors to get right

| Class | Signature |
|---|---|
| `PerspectiveCamera` | `(fov, aspect, near, far)`. `fov` is in degrees. |
| `WebGLRenderer` | `(parameters)`, for example `{ antialias, alpha, canvas }` |
| `WebGPURenderer` | `(parameters)`, then `await renderer.init()` |
| `Mesh` | `(geometry, material)` |

## Common pitfalls

- **Colors look washed out or too dark.** Check `renderer.outputColorSpace`. The default is `SRGBColorSpace`. Color and albedo textures must have `texture.colorSpace = THREE.SRGBColorSpace`. Data textures (normal and roughness maps) stay in the default linear space.
- **Nothing renders.** Common causes: the camera is inside the object, the object is outside the frustum (near/far), the material is `MeshStandardMaterial` with no light, or the canvas has zero size because the container has no height.
- **Aspect ratio stretched after resize.** Update `camera.aspect` and call `camera.updateProjectionMatrix()`.
- **Memory growth.** Call `.dispose()` on geometries, materials, and textures you remove. `renderer.dispose()` releases renderer resources. Removing an object from the scene does not free GPU memory.
- **`WebGPURenderer` renders nothing.** Forgot `await renderer.init()`. Also check that the import map resolves `three/webgpu`.
- **TSL in `WebGLRenderer`.** Node materials need the WebGPU build. Do not mix them.
- **Shadows are missing.** Set `renderer.shadowMap.enabled = true`, `light.castShadow = true`, and `mesh.castShadow` / `mesh.receiveShadow` as needed.
- **Animations are not playing.** Create an `AnimationMixer` per root object, call `mixer.update(delta)` every frame with `clock.getDelta()`, and call `action.play()`.

## Animation loop with delta time

```js
const clock = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const delta = clock.getDelta();
  mixer?.update(delta);
  controls.update();
  renderer.render(scene, camera);
});
```

## Loading models

```js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const loader = new GLTFLoader();
const gltf = await loader.loadAsync('model.glb');
scene.add(gltf.scene);
```

`GLTFLoader` supports `.glb` and `.gltf`. Textures are loaded and decoded asynchronously, so use `loadAsync` and wait before measuring or positioning the model.

## Reviewing three.js code

When reviewing, check these in order:
1. Is the renderer/import combination valid (`three` vs `three/webgpu`, addons path)?
2. Is `setAnimationLoop` used, and does `render` run every frame?
3. Are the resize handler and aspect ratio correct?
4. Are textures in the right color space?
5. Are resources disposed when removed?
6. Is the code reading properties or methods that exist in the target version?

## References

- `references/api-reference.md`: condensed API for the classes most often used.
- The full docs are in the mrdoob/three.js repository under `docs/pages/`. Start from `docs/llms.txt` or `docs/llms-full.txt`, or from `https://threejs.org/docs/llms.txt`.
