// ============================================================
// Avatar3D.tsx
// Avatar 3D rigged dengan ThreeJS + GLB model
// Adaptasi dari repo Kevin Thomas (2D stick figure → 3D GLB)
//
// Perubahan kunci vs repo asli:
//   - THREE.GLTFLoader memuat model .glb dengan rig (SkeletonHelper)
//   - Keyframe 225-dim (vs 63-dim) diapply ke bone hierarchy
//   - AnimationMixer mengelola transisi antar kata
//   - Dukungan 33 pose + 21+21 hand landmarks
// ============================================================

import { useEffect, useRef, useCallback, useState } from "react";
import * as THREE from "three";
// @ts-ignore
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader";
// @ts-ignore
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { AvatarProps, AvatarKeyframe } from "../types/bisindo";

// Mapping landmark index ke nama bone pada GLB model
// Disesuaikan dengan struktur MediaPipe Holistic (225 pts)
const POSE_BONE_MAP: Record<number, string> = {
  0:  "Head",
  11: "LeftUpperArm",
  12: "RightUpperArm",
  13: "LeftLowerArm",
  14: "RightLowerArm",
  15: "LeftHand",
  16: "RightHand",
  23: "LeftUpperLeg",
  24: "RightUpperLeg",
  25: "LeftLowerLeg",
  26: "RightLowerLeg",
};

// 21 landmark tangan → nama bone jari di GLB
const HAND_BONE_PREFIXES = [
  "Wrist", "Thumb0", "Thumb1", "Thumb2", "Thumb3",
  "Index0", "Index1", "Index2", "Index3",
  "Middle0", "Middle1", "Middle2", "Middle3",
  "Ring0", "Ring1", "Ring2", "Ring3",
  "Pinky0", "Pinky1", "Pinky2", "Pinky3",
];

/**
 * Parse flat 225-dim array → AvatarKeyframe struct
 * Layout: [pose_x,y,z ×33] [left_hand_x,y,z ×21] [right_hand_x,y,z ×21]
 */
function parseKeyframe(flat: number[]): AvatarKeyframe {
  return {
    pose:       flat.slice(0, 99),
    left_hand:  flat.slice(99, 162),
    right_hand: flat.slice(162, 225),
  };
}

export default function Avatar3D({ animation, isPlaying, onAnimationEnd }: AvatarProps) {
  const mountRef    = useRef<HTMLDivElement>(null);
  const sceneRef    = useRef<THREE.Scene | null>(null);
  const cameraRef   = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const mixerRef    = useRef<THREE.AnimationMixer | null>(null);
  const modelRef    = useRef<THREE.Object3D | null>(null);
  const bonesRef    = useRef<Map<string, THREE.Bone>>(new Map());
  const frameIdRef  = useRef<number>(0);
  const clockRef    = useRef<THREE.Clock>(new THREE.Clock());
  const [loadError, setLoadError] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const [webglError, setWebglError] = useState(false);

  // ---------- Setup scene ----------
  useEffect(() => {
    if (!mountRef.current) return;
    const el = mountRef.current;

    // Renderer
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch (err) {
      console.error("[Avatar3D] Gagal membuat konteks WebGL:", err);
      setWebglError(true);
      return;
    }
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera (framing torso + tangan)
    const camera = new THREE.PerspectiveCamera(
      45,
      el.clientWidth / el.clientHeight,
      0.1,
      100
    );
    camera.position.set(0, 1.4, 2.8);
    cameraRef.current = camera;

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const dir = new THREE.DirectionalLight(0xffffff, 1.2);
    dir.position.set(2, 4, 3);
    scene.add(dir);

    // OrbitControls (optional, untuk preview)
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.2, 0);
    controls.enablePan = false;
    controls.enableZoom = false;
    controls.update();

    // Load GLB model
    // Letakkan file avatar di public/models/avatar_bisindo.glb
    const loader = new GLTFLoader();
    loader.load(
      "/models/avatar_bisindo.glb",
      (gltf: any) => {
        const model = gltf.scene;
        model.scale.setScalar(1);
        scene.add(model);
        modelRef.current = model;
        setIsLoaded(true);

        // Kumpulkan semua bones ke Map untuk akses O(1)
        const boneMap = new Map<string, THREE.Bone>();
        model.traverse((child: any) => {
          if (child.isBone) {
            let name = child.name;
            boneMap.set(name, child);

            // Jika model dari Mixamo (seperti Xbot)
            if (name.includes('mixamorig:')) {
              name = name.replace('mixamorig:', '');
              
              if (name === 'LeftArm') boneMap.set('LeftUpperArm', child);
              if (name === 'RightArm') boneMap.set('RightUpperArm', child);
              if (name === 'LeftForeArm') boneMap.set('LeftLowerArm', child);
              if (name === 'RightForeArm') boneMap.set('RightLowerArm', child);
              if (name === 'LeftUpLeg') boneMap.set('LeftUpperLeg', child);
              if (name === 'RightUpLeg') boneMap.set('RightUpperLeg', child);
              if (name === 'LeftLeg') boneMap.set('LeftLowerLeg', child);
              if (name === 'RightLeg') boneMap.set('RightLowerLeg', child);
              
              if (name === 'LeftHand') {
                boneMap.set('LeftHand', child);
                boneMap.set('Left_Wrist', child);
              }
              if (name === 'RightHand') {
                boneMap.set('RightHand', child);
                boneMap.set('Right_Wrist', child);
              }

              const handMatch = name.match(/^(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)([1-4])$/);
              if (handMatch) {
                const side = handMatch[1];
                const finger = handMatch[2];
                const index = parseInt(handMatch[3]) - 1;
                boneMap.set(`${side}_${finger}${index}`, child);
              }
              
              if (name === 'Head') boneMap.set('Head', child);
            }
          }
        });
        bonesRef.current = boneMap;

        // AnimationMixer untuk transisi idle
        const mixer = new THREE.AnimationMixer(model);
        mixerRef.current = mixer;

        // Putar animasi idle jika ada di file GLB
        if (gltf.animations.length > 0) {
          const idleClip = gltf.animations.find((a: any) => a.name === "Idle");
          if (idleClip) {
            mixer.clipAction(idleClip).play();
          }
        }
      },
      undefined,
      (err: any) => {
        console.error("[Avatar3D] Gagal load GLB:", err);
        setLoadError(true);
      }
    );

    // Render loop
    const animate = () => {
      frameIdRef.current = requestAnimationFrame(animate);
      const delta = clockRef.current.getDelta();
      mixerRef.current?.update(delta);
      renderer.render(scene, camera);
    };
    animate();

    // Resize handler
    const onResize = () => {
      if (!el) return;
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(frameIdRef.current);
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  // ---------- Apply keyframes when animation arrives ----------
  const applyKeyframe = useCallback((flat: number[]) => {
    if (!modelRef.current || bonesRef.current.size === 0) return;

    const kf = parseKeyframe(flat);
    const bones = bonesRef.current;

    // 1. Pose landmarks → upper body bones
    for (const [idx, boneName] of Object.entries(POSE_BONE_MAP)) {
      const bone = bones.get(boneName);
      if (!bone) continue;
      const i = parseInt(idx) * 3;
      const x = kf.pose[i];
      const y = kf.pose[i + 1];
      const z = kf.pose[i + 2];
      if (x === undefined) continue;

      // Konversi landmark space → bone rotation
      // MediaPipe: y naik = turun layar; x = horizontal (kiri-kanan)
      bone.rotation.x = -y * Math.PI;
      bone.rotation.y = x * Math.PI;
      bone.rotation.z = z * 0.5;
    }

    // 2. Left hand landmarks → LeftHand bone hierarchy
    for (let i = 0; i < 21; i++) {
      const boneName = `Left_${HAND_BONE_PREFIXES[i]}`;
      const bone = bones.get(boneName);
      if (!bone) continue;
      const x = kf.left_hand[i * 3];
      const y = kf.left_hand[i * 3 + 1];
      bone.rotation.x = -y * Math.PI * 0.5;
      bone.rotation.z = x * Math.PI * 0.3;
    }

    // 3. Right hand landmarks
    for (let i = 0; i < 21; i++) {
      const boneName = `Right_${HAND_BONE_PREFIXES[i]}`;
      const bone = bones.get(boneName);
      if (!bone) continue;
      const x = kf.right_hand[i * 3];
      const y = kf.right_hand[i * 3 + 1];
      bone.rotation.x = -y * Math.PI * 0.5;
      bone.rotation.z = x * Math.PI * 0.3;
    }
  }, []);

  // ---------- Play animation when new sign arrives ----------
  useEffect(() => {
    if (!animation || !isPlaying) return;

    const { frames, fps } = animation;
    const msPerFrame = 1000 / (fps || 30);
    let frameIdx = 0;

    const playNext = () => {
      if (frameIdx >= frames.length) {
        onAnimationEnd?.();
        return;
      }
      applyKeyframe(frames[frameIdx]);
      frameIdx++;
      setTimeout(playNext, msPerFrame);
    };

    playNext();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [animation, isPlaying]);

  return (
    <div className="relative w-full h-full min-h-[280px] bg-gray-950 rounded-2xl overflow-hidden">
      {/* Three.js canvas container */}
      <div ref={mountRef} className="w-full h-full" />

      {/* Word overlay (kata yang sedang diperagakan) */}
      {animation && isPlaying && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2
                        px-4 py-1.5 rounded-full bg-black/60 backdrop-blur-sm
                        border border-white/10 text-white text-sm font-medium">
          {animation.word}
          {animation.fingerspell && (
            <span className="ml-2 text-[10px] text-white/50">(fingerspell)</span>
          )}
        </div>
      )}

      {/* Loading placeholder (sebelum GLB dimuat) */}
      {!isLoaded && !loadError && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="text-4xl mb-3 animate-pulse">🤟</div>
            <p className="text-xs text-white/40">Memuat avatar BISINDO…</p>
          </div>
        </div>
      )}

      {/* Error placeholder (jika GLB gagal dimuat) */}
      {loadError && !webglError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 px-4">
          <span className="text-4xl mb-2">⚠️</span>
          <p className="text-sm font-bold text-red-400 mb-1">Avatar 3D Tidak Ditemukan</p>
          <p className="text-[10px] text-white/60 text-center">
            Sistem tidak dapat menemukan file 3D model di path:<br/>
            <code className="text-yellow-300">public/models/avatar_bisindo.glb</code><br/>
            Harap masukkan file GLB avatar yang memiliki struktur tulang (rigged) yang sesuai.
          </p>
        </div>
      )}

      {/* WebGL Error fallback */}
      {webglError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 px-4">
          <span className="text-4xl mb-2">💻</span>
          <p className="text-sm font-bold text-red-400 mb-1">WebGL Tidak Didukung</p>
          <p className="text-[10px] text-white/60 text-center">
            Peramban (browser) atau kartu grafismu gagal memuat konteks 3D (WebGL).<br/>
            Avatar tidak dapat dirender. Fitur lainnya akan tetap berjalan normal.
          </p>
        </div>
      )}
    </div>
  );
}
