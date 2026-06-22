"use client";

import type { SimulateResponse } from "@restart/shared-types";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { CAMERA_PRESETS, frameIndex, worldToScene, type CameraPreset } from "./replay3d-util";

// Tier-2 3D replay (doc 07 §3). Consumes the SAME SimulateResponse the 2D
// ReplayPlayer uses — ball_path carries z so the flight arc is real; player
// tracks are 2D and sit on the ground plane. Loaded on demand (dynamic import)
// so R3F/three never enter the default bundle.

export interface Replay3DProps {
  data: SimulateResponse;
  preset: CameraPreset;
  /** Honor prefers-reduced-motion: freeze on the contact frame, no animation. */
  reducedMotion?: boolean;
}

const SIGNAL = "#00e07b"; // attacking
const RISK = "#f5a524"; // defending
const FROZEN_PROGRESS = 0.6; // ~ the delivery's first contact

function CameraRig({ preset }: { preset: CameraPreset }) {
  const { camera } = useThree();
  useEffect(() => {
    const { position, target } = CAMERA_PRESETS[preset];
    camera.position.set(...position);
    camera.lookAt(...target);
  }, [camera, preset]);
  return null;
}

function Scene({ data, reducedMotion }: { data: SimulateResponse; reducedMotion: boolean }) {
  const nAtt = data.att_tracks[0]?.length ?? 0;
  const nDef = data.def_tracks[0]?.length ?? 0;
  const totalT = data.track_times_s[data.track_times_s.length - 1] || 1;

  const attRefs = useRef<(THREE.Mesh | null)[]>([]);
  const defRefs = useRef<(THREE.Mesh | null)[]>([]);
  const ballRef = useRef<THREE.Mesh>(null);
  // Lazily stamped on the first frame — calling performance.now() in the ref
  // initializer is an impure call during render (react-compiler lint).
  const startRef = useRef<number | null>(null);

  // The ball flight as a real 3D line through ball_path (a primitive so we keep
  // clear of fragile <line> JSX typing).
  const trajectory = useMemo(() => {
    const pts = data.ball_path.map((p) => new THREE.Vector3(...worldToScene(p)));
    const geom = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: SIGNAL, opacity: 0.5, transparent: true });
    return new THREE.Line(geom, mat);
  }, [data]);

  useFrame(() => {
    startRef.current ??= performance.now();
    const p = reducedMotion
      ? FROZEN_PROGRESS
      : (((performance.now() - startRef.current) / 1000) % totalT) / totalT;

    const ti = frameIndex(p, data.track_times_s.length);
    data.att_tracks[ti]?.forEach((pt, i) => {
      const s = worldToScene(pt);
      attRefs.current[i]?.position.set(s[0], 0.4, s[2]);
    });
    data.def_tracks[ti]?.forEach((pt, i) => {
      const s = worldToScene(pt);
      defRefs.current[i]?.position.set(s[0], 0.4, s[2]);
    });
    const bi = frameIndex(p, data.ball_path.length);
    const bp = data.ball_path[bi];
    if (bp && ballRef.current) {
      const s = worldToScene(bp);
      ballRef.current.position.set(s[0], Math.max(0.12, s[1]), s[2]);
    }
  });

  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight position={[10, 20, 10]} intensity={1.1} />

      {/* Pitch ground (goal at z=0, play arrives from +z). */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 12]} receiveShadow>
        <planeGeometry args={[60, 44]} />
        <meshStandardMaterial color="#0e1a12" />
      </mesh>

      {/* Goal frame: 7.32 m wide, 2.44 m tall, on the goal line. */}
      <group>
        <mesh position={[-3.66, 1.22, 0]}>
          <boxGeometry args={[0.12, 2.44, 0.12]} />
          <meshStandardMaterial color="#cfd8d3" />
        </mesh>
        <mesh position={[3.66, 1.22, 0]}>
          <boxGeometry args={[0.12, 2.44, 0.12]} />
          <meshStandardMaterial color="#cfd8d3" />
        </mesh>
        <mesh position={[0, 2.44, 0]}>
          <boxGeometry args={[7.44, 0.12, 0.12]} />
          <meshStandardMaterial color="#cfd8d3" />
        </mesh>
      </group>

      {Array.from({ length: nAtt }).map((_, i) => (
        <mesh key={`a${i}`} ref={(m) => void (attRefs.current[i] = m)}>
          <sphereGeometry args={[0.5, 16, 16]} />
          <meshStandardMaterial color={SIGNAL} />
        </mesh>
      ))}
      {Array.from({ length: nDef }).map((_, i) => (
        <mesh key={`d${i}`} ref={(m) => void (defRefs.current[i] = m)}>
          <sphereGeometry args={[0.5, 16, 16]} />
          <meshStandardMaterial color={RISK} />
        </mesh>
      ))}

      <primitive object={trajectory} />
      <mesh ref={ballRef}>
        <sphereGeometry args={[0.22, 16, 16]} />
        <meshStandardMaterial color="#ffffff" />
      </mesh>
    </>
  );
}

export default function Replay3D({ data, preset, reducedMotion = false }: Replay3DProps) {
  return (
    <div className="h-[420px] w-full overflow-hidden rounded-lg border border-(--color-line)/15">
      <Canvas camera={{ fov: 45, position: CAMERA_PRESETS[preset].position }} dpr={[1, 2]}>
        <color attach="background" args={["#0b0f0d"]} />
        <CameraRig preset={preset} />
        <Scene data={data} reducedMotion={reducedMotion} />
      </Canvas>
    </div>
  );
}
