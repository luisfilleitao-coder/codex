# three.js API reference (condensed, r187)

Source: `docs/pages/*.md` in mrdoob/three.js at version 0.187.0. This is a condensed guide. For exact defaults and full property lists, read the page for the class.

## Core scene graph

| Class | Purpose | Notes |
|---|---|---|
| `Scene` | Root of the scene graph | `background` (Color, Texture, or cube/equirect for a skybox), `environment` (env map for physical materials), `environmentIntensity`, `backgroundBlurriness` |
| `Object3D` | Base class for everything in the scene | `position`, `rotation` (Euler, radians), `quaternion`, `scale`, `add()`, `remove()`, `traverse()`, `clone()` |
| `Group` | Empty container for transforms | Use it to move several objects together |
| `Mesh` | Geometry plus material | `new Mesh(geometry, material)`, `castShadow`, `receiveShadow` |
| `Points`, `Line`, `LineSegments` | Point and line primitives | Same constructor pattern as `Mesh` |

## Cameras

| Class | Constructor | Notes |
|---|---|---|
| `PerspectiveCamera` | `(fov, aspect, near, far)` | `fov` in degrees. Call `updateProjectionMatrix()` after changing `fov`, `aspect`, `near` or `far`. |
| `OrthographicCamera` | `(left, right, top, bottom, near, far)` | Use for 2D views or CAD-like views. |
| `ArrayCamera` | Array of sub-cameras | Multi-view rendering. |

Position the camera with `camera.position.set(x, y, z)` and aim it with `camera.lookAt(x, y, z)`.

## Renderers

### WebGLRenderer

`new WebGLRenderer({ antialias, alpha, canvas, powerPreference, preserveDrawingBuffer })`

| Member | Notes |
|---|---|
| `setSize(w, h, updateStyle?)` | Resizes the drawing buffer. |
| `setPixelRatio(v)` | Use `Math.min(devicePixelRatio, 2)` as a common cap. |
| `setAnimationLoop(fn)` | Pass `null` to stop. Works with XR. |
| `render(scene, camera)` | Draws one frame. |
| `outputColorSpace` | Default `SRGBColorSpace`. |
| `shadowMap.enabled`, `shadowMap.type` | Enables shadow maps. |
| `domElement` | The `<canvas>` to add to the page. |
| `dispose()` | Releases renderer resources. |

### WebGPURenderer (`three/webgpu`)

`new WebGPURenderer({ antialias, forceWebGL, ... })`

- `await renderer.init()` is required before rendering.
- Falls back to a WebGL 2 backend if WebGPU is unavailable. Set `forceWebGL: true` to force that backend.
- Use the same `setSize`, `setPixelRatio`, `setAnimationLoop`, and `render` as `WebGLRenderer`.
- Works with TSL node materials.

## Geometry

Built-in geometries include `BoxGeometry(w, h, d)`, `SphereGeometry(r, widthSeg, heightSeg)`, `PlaneGeometry(w, h)`, `CylinderGeometry`, `TorusGeometry`, `TorusKnotGeometry`, `IcosahedronGeometry`, and `ExtrudeGeometry`.

`BufferGeometry` is the base class for custom geometry. Set attributes with `geometry.setAttribute('position', new THREE.Float32BufferAttribute(array, 3))` and call `geometry.computeVertexNormals()` when normals are missing.

## Materials

| Material | Lit by lights | Use |
|---|---|---|
| `MeshBasicMaterial` | No | Flat color, unlit, debug |
| `MeshLambertMaterial` | Yes | Cheap diffuse lighting |
| `MeshPhongMaterial` | Yes | Shiny specular highlights |
| `MeshStandardMaterial` | Yes | PBR, the default for most scenes. Uses `roughness` and `metalness`. |
| `MeshPhysicalMaterial` | Yes | `MeshStandardMaterial` plus clearcoat, transmission, sheen |
| `MeshNormalMaterial` | No | Debugging normals |

Texture maps: `map` (color, sRGB), `normalMap`, `roughnessMap`, `metalnessMap`, `aoMap`, `emissiveMap`, `envMap`. Set `texture.colorSpace = THREE.SRGBColorSpace` for color maps only.

## Lights

| Light | Notes |
|---|---|
| `AmbientLight(color, intensity)` | Uniform fill. No direction. |
| `DirectionalLight(color, intensity)` | Sun-like. Position it and set its `target`. Supports shadows. |
| `PointLight(color, intensity, distance, decay)` | Omnidirectional. Supports shadows. |
| `SpotLight(color, intensity, distance, angle, penumbra, decay)` | Cone. Supports shadows. |
| `HemisphereLight(skyColor, groundColor, intensity)` | Sky and ground fill. |

Physical materials need light, or an `environment` map on the scene, to look correct.

## Textures and loading

- `TextureLoader().loadAsync(url)` returns a `Texture`.
- `CubeTextureLoader` loads six-face skyboxes.
- `GLTFLoader` (`three/addons/loaders/GLTFLoader.js`) loads glTF and GLB. The result has `gltf.scene`, `gltf.animations`, and `gltf.cameras`.
- `RGBELoader` (addons) loads HDR environment maps.

## Animation

- `AnimationMixer(root)`. Call `mixer.update(delta)` each frame.
- `mixer.clipAction(clip).play()` starts a clip. `AnimationClip` comes from `gltf.animations`.
- Use `THREE.Clock.getDelta()` for `delta`.

## Controls (addons)

| Control | Import | Notes |
|---|---|---|
| `OrbitControls` | `three/addons/controls/OrbitControls.js` | Most common. Needs `controls.update()` in the loop when `enableDamping` is on. |
| `TrackballControls`, `ArcballControls` | Same folder | Free rotation. |
| `FirstPersonControls`, `FlyControls`, `PointerLockControls` | Same folder | Game-style navigation. |
| `TransformControls`, `DragControls` | Same folder | Editing and dragging objects. |

Example:

```js
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
// in the loop: controls.update();
```

## Raycasting (picking objects with the mouse)

```js
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
renderer.domElement.addEventListener('pointermove', (e) => {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(scene.children, true);
});
```

## Disposal checklist

When removing an object permanently:
1. `mesh.removeFromParent()` (or `scene.remove(mesh)`)
2. `mesh.geometry.dispose()`
3. `mesh.material.dispose()`, plus `dispose()` on each texture in the material's maps
4. Call `dispose()` on controls and loaders that hold listeners or workers

## TSL (`three/tsl`, WebGPU only)

Common exports verified in `build/three.tsl.js`: `Fn`, `uniform`, `texture`, `uv`, `float`, `vec3`, `mix`, `time`, `oscSine`, `positionLocal`, `normalWorld`.

Example: a color that pulses over time, applied to a `MeshStandardNodeMaterial` (import from `three/webgpu`).

```js
import * as THREE from 'three/webgpu';
import { vec3, oscSine, time, mix } from 'three/tsl';

const material = new THREE.MeshStandardNodeMaterial();
const base = vec3(0.2, 0.5, 1.0);
const pulse = oscSine(time);
material.colorNode = mix(base, vec3(1, 0.3, 0.1), pulse);
```

Check the exact node names in `docs/pages/` before using a less common one, because the TSL API has changed between releases.
