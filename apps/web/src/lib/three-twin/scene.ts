/**
 * Vanilla Three.js scene, managed imperatively (no React reconciler).
 *
 * @react-three/fiber v8 (installed) requires React 18's reconciler internals
 * and crashes on import under this project's React 19 (`Cannot read
 * properties of undefined (reading 'ReactCurrentOwner')`, confirmed by
 * actually trying it) — fiber v9 is the React-19-compatible line but
 * upgrading mid-build risked cascading breaking changes across fiber+drei.
 * Plain `three` has zero React-version coupling, so this class owns the
 * renderer/scene/camera/loop directly; DigitalTwinCanvas.tsx (the thin React
 * wrapper) just gives it a container div and forwards snapshot updates.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { PointerLockControls } from 'three/examples/jsm/controls/PointerLockControls.js';

export type NavigationMode = 'orbit' | 'walk';

const WALK_SPEED = 6; // meters/second
const WALK_EYE_HEIGHT = 1.7;

export class DigitalTwinScene {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene: THREE.Scene;
  readonly camera: THREE.PerspectiveCamera;
  readonly orbitControls: OrbitControls;
  readonly pointerLockControls: PointerLockControls;

  private container: HTMLElement;
  private animationFrame: number | null = null;
  private resizeObserver: ResizeObserver;
  private clock = new THREE.Clock();
  private mode: NavigationMode = 'orbit';
  private walkKeys = { forward: false, back: false, left: false, right: false };
  private walkVelocity = new THREE.Vector3();
  private onTick: ((deltaSeconds: number) => void) | null = null;

  constructor(container: HTMLElement) {
    this.container = container;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#0A0C0F');
    this.scene.fog = new THREE.Fog('#0A0C0F', 60, 220);

    this.camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 1000);
    this.camera.position.set(0, 45, 55);

    this.orbitControls = new OrbitControls(this.camera, this.renderer.domElement);
    this.orbitControls.enableDamping = true;
    this.orbitControls.dampingFactor = 0.08;
    this.orbitControls.maxPolarAngle = Math.PI * 0.49; // never let the camera tip below the ground plane
    this.orbitControls.minDistance = 3;
    this.orbitControls.maxDistance = 160;

    this.pointerLockControls = new PointerLockControls(this.camera, this.renderer.domElement);

    this._setupLights();
    this._setupGround();

    this.resizeObserver = new ResizeObserver(() => this._onResize());
    this.resizeObserver.observe(container);

    window.addEventListener('keydown', this._onKeyDown);
    window.addEventListener('keyup', this._onKeyUp);

    this._animate = this._animate.bind(this);
    this.animationFrame = requestAnimationFrame(this._animate);
  }

  private _setupLights() {
    const ambient = new THREE.AmbientLight('#8892b0', 0.55);
    this.scene.add(ambient);

    const sun = new THREE.DirectionalLight('#fff2d6', 1.1);
    sun.position.set(80, 120, 40);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left = -100;
    sun.shadow.camera.right = 100;
    sun.shadow.camera.top = 100;
    sun.shadow.camera.bottom = -100;
    sun.shadow.camera.far = 300;
    this.scene.add(sun);

    const hemi = new THREE.HemisphereLight('#3a4a6b', '#0a0c0f', 0.4);
    this.scene.add(hemi);
  }

  private _setupGround() {
    const groundGeometry = new THREE.PlaneGeometry(400, 400);
    const groundMaterial = new THREE.MeshStandardMaterial({ color: '#14171d', roughness: 0.95, metalness: 0.05 });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    ground.name = 'ground';
    this.scene.add(ground);

    const grid = new THREE.GridHelper(400, 80, '#252A31', '#1A1E24');
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.6;
    this.scene.add(grid);
  }

  private _onResize() {
    const { clientWidth, clientHeight } = this.container;
    if (clientWidth === 0 || clientHeight === 0) return;
    this.camera.aspect = clientWidth / clientHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(clientWidth, clientHeight);
  }

  private _onKeyDown = (e: KeyboardEvent) => {
    switch (e.code) {
      case 'KeyW':
      case 'ArrowUp':
        this.walkKeys.forward = true;
        break;
      case 'KeyS':
      case 'ArrowDown':
        this.walkKeys.back = true;
        break;
      case 'KeyA':
      case 'ArrowLeft':
        this.walkKeys.left = true;
        break;
      case 'KeyD':
      case 'ArrowRight':
        this.walkKeys.right = true;
        break;
    }
  };

  private _onKeyUp = (e: KeyboardEvent) => {
    switch (e.code) {
      case 'KeyW':
      case 'ArrowUp':
        this.walkKeys.forward = false;
        break;
      case 'KeyS':
      case 'ArrowDown':
        this.walkKeys.back = false;
        break;
      case 'KeyA':
      case 'ArrowLeft':
        this.walkKeys.left = false;
        break;
      case 'KeyD':
      case 'ArrowRight':
        this.walkKeys.right = false;
        break;
    }
  };

  setNavigationMode(mode: NavigationMode) {
    this.mode = mode;
    if (mode === 'walk') {
      this.orbitControls.enabled = false;
      this.camera.position.y = WALK_EYE_HEIGHT;
      this.pointerLockControls.lock();
    } else {
      this.pointerLockControls.unlock();
      this.orbitControls.enabled = true;
    }
  }

  get navigationMode(): NavigationMode {
    return this.mode;
  }

  /** Registers the per-frame update callback (object animation, position lerps, etc.) driven by DigitalTwinCanvas. */
  setTickHandler(handler: (deltaSeconds: number) => void) {
    this.onTick = handler;
  }

  private _stepWalk(delta: number) {
    if (this.mode !== 'walk' || !this.pointerLockControls.isLocked) return;
    const damping = Math.max(0, 1 - delta * 6);
    this.walkVelocity.x *= damping;
    this.walkVelocity.z *= damping;

    const forwardInput = Number(this.walkKeys.forward) - Number(this.walkKeys.back);
    const rightInput = Number(this.walkKeys.right) - Number(this.walkKeys.left);
    this.walkVelocity.z -= forwardInput * WALK_SPEED * delta * 8;
    this.walkVelocity.x -= rightInput * WALK_SPEED * delta * 8;
    this.walkVelocity.x = THREE.MathUtils.clamp(this.walkVelocity.x, -WALK_SPEED, WALK_SPEED);
    this.walkVelocity.z = THREE.MathUtils.clamp(this.walkVelocity.z, -WALK_SPEED, WALK_SPEED);

    this.pointerLockControls.moveRight(-this.walkVelocity.x * delta);
    this.pointerLockControls.moveForward(-this.walkVelocity.z * delta);
    this.camera.position.y = WALK_EYE_HEIGHT; // stay at eye height -- no flying, no falling through the floor
  }

  private _animate() {
    this.animationFrame = requestAnimationFrame(this._animate);
    const delta = Math.min(this.clock.getDelta(), 0.1);

    if (this.mode === 'orbit') {
      this.orbitControls.update();
    } else {
      this._stepWalk(delta);
    }

    this.onTick?.(delta);
    this.renderer.render(this.scene, this.camera);
  }

  /** Raycasts from a client-space (x, y) point and returns the first intersected object with userData.mapObjectId set. */
  pick(clientX: number, clientY: number): THREE.Object3D | null {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((clientX - rect.left) / rect.width) * 2 - 1,
      -((clientY - rect.top) / rect.height) * 2 + 1,
    );
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, this.camera);
    const intersects = raycaster.intersectObjects(this.scene.children, true);
    for (const hit of intersects) {
      let obj: THREE.Object3D | null = hit.object;
      while (obj) {
        if (obj.userData.mapObjectKind) return obj;
        obj = obj.parent;
      }
    }
    return null;
  }

  dispose() {
    if (this.animationFrame !== null) cancelAnimationFrame(this.animationFrame);
    this.resizeObserver.disconnect();
    window.removeEventListener('keydown', this._onKeyDown);
    window.removeEventListener('keyup', this._onKeyUp);
    this.pointerLockControls.unlock();
    this.pointerLockControls.dispose();
    this.orbitControls.dispose();

    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        const materials = Array.isArray(obj.material) ? obj.material : [obj.material];
        materials.forEach((m) => m.dispose());
      }
    });

    this.renderer.dispose();
    if (this.renderer.domElement.parentElement === this.container) {
      this.container.removeChild(this.renderer.domElement);
    }
  }
}
