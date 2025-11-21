#!/usr/bin/env python3
"""
Annotation Analysis Script

Analyzes all annotation JSON files to extract comprehensive statistics about
detected objects, including HSV ranges, position distributions, size ranges,
and shape characteristics. Compares with current detector configuration and
provides optimization recommendations.

Usage:
    python scripts/analyze_annotations.py
    python scripts/analyze_annotations.py --samples-dir /path/to/samples
    python scripts/analyze_annotations.py --export-csv results.csv
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

# Try to import detector config
try:
    from msmacro.cv.detection_config import load_config
    HAS_DETECTOR_CONFIG = True
except ImportError:
    HAS_DETECTOR_CONFIG = False


@dataclass
class ObjectStats:
    """Statistics for a single object type."""
    object_type: str
    count: int = 0

    # Position statistics
    x_values: List[int] = field(default_factory=list)
    y_values: List[int] = field(default_factory=list)

    # HSV statistics
    h_values: List[int] = field(default_factory=list)
    s_values: List[int] = field(default_factory=list)
    v_values: List[int] = field(default_factory=list)

    # Size statistics
    radius_values: List[float] = field(default_factory=list)
    width_values: List[int] = field(default_factory=list)
    height_values: List[int] = field(default_factory=list)

    # Shape statistics
    circularity_values: List[float] = field(default_factory=list)
    aspect_ratio_values: List[float] = field(default_factory=list)

    def add_annotation(self, ann: Dict[str, Any]):
        """Add an annotation to statistics."""
        self.count += 1

        # Position
        if 'x' in ann and 'y' in ann:
            self.x_values.append(ann['x'])
            self.y_values.append(ann['y'])

        # HSV
        if 'hsv_h' in ann:
            self.h_values.append(ann['hsv_h'])
        if 'hsv_s' in ann:
            self.s_values.append(ann['hsv_s'])
        if 'hsv_v' in ann:
            self.v_values.append(ann['hsv_v'])

        # Size
        if 'radius' in ann:
            self.radius_values.append(ann['radius'])
        if 'width' in ann:
            self.width_values.append(ann['width'])
        if 'height' in ann:
            self.height_values.append(ann['height'])

        # Shape
        if 'circularity' in ann:
            self.circularity_values.append(ann['circularity'])
        if 'aspect_ratio' in ann:
            self.aspect_ratio_values.append(ann['aspect_ratio'])

    def compute_statistics(self) -> Dict[str, Any]:
        """Compute summary statistics."""
        stats = {
            'count': self.count,
            'object_type': self.object_type
        }

        # Position statistics
        if self.x_values:
            stats['position'] = {
                'x': {
                    'min': int(np.min(self.x_values)),
                    'max': int(np.max(self.x_values)),
                    'mean': float(np.mean(self.x_values)),
                    'std': float(np.std(self.x_values))
                },
                'y': {
                    'min': int(np.min(self.y_values)),
                    'max': int(np.max(self.y_values)),
                    'mean': float(np.mean(self.y_values)),
                    'std': float(np.std(self.y_values))
                }
            }

        # HSV statistics
        if self.h_values:
            stats['hsv'] = {
                'hue': {
                    'min': int(np.min(self.h_values)),
                    'max': int(np.max(self.h_values)),
                    'mean': float(np.mean(self.h_values)),
                    'std': float(np.std(self.h_values)),
                    'recommended_range': (
                        max(0, int(np.mean(self.h_values) - 2 * np.std(self.h_values))),
                        min(179, int(np.mean(self.h_values) + 2 * np.std(self.h_values)))
                    )
                }
            }

        if self.s_values:
            stats['hsv']['saturation'] = {
                'min': int(np.min(self.s_values)),
                'max': int(np.max(self.s_values)),
                'mean': float(np.mean(self.s_values)),
                'std': float(np.std(self.s_values)),
                'recommended_range': (
                    max(0, int(np.mean(self.s_values) - 2 * np.std(self.s_values))),
                    min(255, int(np.mean(self.s_values) + 2 * np.std(self.s_values)))
                )
            }

        if self.v_values:
            stats['hsv']['value'] = {
                'min': int(np.min(self.v_values)),
                'max': int(np.max(self.v_values)),
                'mean': float(np.mean(self.v_values)),
                'std': float(np.std(self.v_values)),
                'recommended_range': (
                    max(0, int(np.mean(self.v_values) - 2 * np.std(self.v_values))),
                    min(255, int(np.mean(self.v_values) + 2 * np.std(self.v_values)))
                )
            }

        # Size statistics
        if self.radius_values:
            radii = np.array(self.radius_values)
            diameters = radii * 2
            stats['size'] = {
                'radius': {
                    'min': float(np.min(radii)),
                    'max': float(np.max(radii)),
                    'mean': float(np.mean(radii)),
                    'std': float(np.std(radii))
                },
                'diameter': {
                    'min': float(np.min(diameters)),
                    'max': float(np.max(diameters)),
                    'mean': float(np.mean(diameters)),
                    'std': float(np.std(diameters)),
                    'recommended_range': (
                        max(2, int(np.mean(diameters) - 2 * np.std(diameters))),
                        min(50, int(np.mean(diameters) + 2 * np.std(diameters)))
                    )
                }
            }

        # Shape statistics
        if self.circularity_values:
            stats['shape'] = {
                'circularity': {
                    'min': float(np.min(self.circularity_values)),
                    'max': float(np.max(self.circularity_values)),
                    'mean': float(np.mean(self.circularity_values)),
                    'std': float(np.std(self.circularity_values)),
                    'recommended_threshold': float(np.mean(self.circularity_values) - 2 * np.std(self.circularity_values))
                }
            }

        if self.aspect_ratio_values:
            if 'shape' not in stats:
                stats['shape'] = {}
            stats['shape']['aspect_ratio'] = {
                'min': float(np.min(self.aspect_ratio_values)),
                'max': float(np.max(self.aspect_ratio_values)),
                'mean': float(np.mean(self.aspect_ratio_values)),
                'std': float(np.std(self.aspect_ratio_values))
            }

        return stats


def find_annotation_files(samples_dir: Path) -> List[Path]:
    """Find all annotation JSON files in directory."""
    return list(samples_dir.glob("*.annotations.json"))


def find_image_files(samples_dir: Path) -> List[Path]:
    """Find all image files in directory."""
    images = []
    for ext in ['*.png', '*.jpg', '*.jpeg']:
        images.extend(samples_dir.glob(ext))
    return images


def load_annotation(file_path: Path) -> Dict[str, Any]:
    """Load annotation from JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def analyze_annotations(samples_dir: Path) -> Tuple[Dict[str, ObjectStats], Dict[str, Any]]:
    """Analyze all annotations and return statistics."""

    # Find files
    annotation_files = find_annotation_files(samples_dir)
    image_files = find_image_files(samples_dir)

    print(f"\n{'='*70}")
    print("ANNOTATION ANALYSIS")
    print('='*70)
    print(f"\nSamples directory: {samples_dir}")
    print(f"Total image files: {len(image_files)}")
    print(f"Annotation files: {len(annotation_files)}")
    print(f"Images without annotations: {len(image_files) - len(annotation_files)}")

    # Statistics by object type
    stats_by_type = defaultdict(lambda: ObjectStats('unknown'))

    # Overall counts
    total_annotations = 0
    files_with_player = 0
    files_with_enemy = 0

    # Process each annotation file
    for ann_file in annotation_files:
        data = load_annotation(ann_file)

        annotations = data.get('annotations', [])
        if not annotations:
            continue

        total_annotations += len(annotations)

        # Track file-level counts
        has_player = False
        has_enemy = False

        for ann in annotations:
            obj_type = ann.get('type', 'unknown')

            if obj_type not in stats_by_type:
                stats_by_type[obj_type] = ObjectStats(obj_type)

            stats_by_type[obj_type].add_annotation(ann)

            if obj_type == 'player':
                has_player = True
            elif obj_type == 'enemy':
                has_enemy = True

        if has_player:
            files_with_player += 1
        if has_enemy:
            files_with_enemy += 1

    # Summary statistics
    summary = {
        'total_image_files': len(image_files),
        'total_annotation_files': len(annotation_files),
        'images_without_annotations': len(image_files) - len(annotation_files),
        'total_annotations': total_annotations,
        'files_with_player': files_with_player,
        'files_with_enemy': files_with_enemy,
        'object_types': list(stats_by_type.keys())
    }

    return dict(stats_by_type), summary


def compare_with_current_config(stats: Dict[str, ObjectStats]):
    """Compare annotation statistics with current detector configuration."""
    if not HAS_DETECTOR_CONFIG:
        print("\n⚠️  Cannot load detector config for comparison")
        return

    try:
        config = load_config()

        print("\n" + "="*70)
        print("COMPARISON WITH CURRENT DETECTOR CONFIG")
        print("="*70)

        # Player HSV comparison
        if 'player' in stats:
            player_stats = stats['player'].compute_statistics()

            if 'hsv' in player_stats:
                print("\n📊 Player HSV Ranges:")
                print(f"\n  Current Config:")
                print(f"    Hue:        {config.player_hue_lower}-{config.player_hue_upper}")
                print(f"    Saturation: {config.player_sat_lower}-255")
                print(f"    Value:      {config.player_val_lower}-255")

                print(f"\n  Annotation Data:")
                hsv = player_stats['hsv']
                if 'hue' in hsv:
                    h_rec = hsv['hue']['recommended_range']
                    print(f"    Hue:        {h_rec[0]}-{h_rec[1]} (mean±2σ: {hsv['hue']['mean']:.1f}±{hsv['hue']['std']*2:.1f})")
                if 'saturation' in hsv:
                    s_rec = hsv['saturation']['recommended_range']
                    print(f"    Saturation: {s_rec[0]}-{s_rec[1]} (mean±2σ: {hsv['saturation']['mean']:.1f}±{hsv['saturation']['std']*2:.1f})")
                if 'value' in hsv:
                    v_rec = hsv['value']['recommended_range']
                    print(f"    Value:      {v_rec[0]}-{v_rec[1]} (mean±2σ: {hsv['value']['mean']:.1f}±{hsv['value']['std']*2:.1f})")

                # Recommendations
                print(f"\n  💡 Recommendations:")
                if 'hue' in hsv:
                    h_rec = hsv['hue']['recommended_range']
                    if h_rec[0] > config.player_hue_lower or h_rec[1] < config.player_hue_upper:
                        print(f"    ⚠️  Consider tightening hue range to {h_rec[0]}-{h_rec[1]}")
                    else:
                        print(f"    ✅ Hue range is appropriate")

                if 'saturation' in hsv:
                    s_rec = hsv['saturation']['recommended_range']
                    if s_rec[0] > config.player_sat_lower:
                        print(f"    ⚠️  Consider increasing saturation minimum to {s_rec[0]}")
                    else:
                        print(f"    ✅ Saturation minimum is appropriate")

                if 'value' in hsv:
                    v_rec = hsv['value']['recommended_range']
                    if v_rec[0] > config.player_val_lower:
                        print(f"    ⚠️  Consider increasing value minimum to {v_rec[0]}")
                    else:
                        print(f"    ✅ Value minimum is appropriate")

        # Size comparison
        if 'player' in stats:
            player_stats = stats['player'].compute_statistics()

            if 'size' in player_stats:
                print("\n📊 Player Size Ranges:")
                print(f"\n  Current Config:")
                print(f"    Diameter: {config.player_dot_min_diameter}-{config.player_dot_max_diameter}px")

                print(f"\n  Annotation Data:")
                size = player_stats['size']
                diam_rec = size['diameter']['recommended_range']
                print(f"    Diameter: {diam_rec[0]}-{diam_rec[1]}px (mean±2σ: {size['diameter']['mean']:.1f}±{size['diameter']['std']*2:.1f})")

                print(f"\n  💡 Recommendations:")
                if diam_rec[0] > config.player_dot_min_diameter or diam_rec[1] < config.player_dot_max_diameter:
                    print(f"    ⚠️  Consider updating diameter range to {diam_rec[0]}-{diam_rec[1]}px")
                else:
                    print(f"    ✅ Diameter range is appropriate")

        # Shape comparison
        if 'player' in stats:
            player_stats = stats['player'].compute_statistics()

            if 'shape' in player_stats and 'circularity' in player_stats['shape']:
                print("\n📊 Player Shape Thresholds:")
                print(f"\n  Current Config:")
                print(f"    Circularity: ≥{config.player_circularity_threshold}")

                print(f"\n  Annotation Data:")
                circ = player_stats['shape']['circularity']
                circ_rec = circ['recommended_threshold']
                print(f"    Circularity: ≥{circ_rec:.2f} (mean-2σ: {circ['mean']:.2f}-{circ['std']*2:.2f})")

                print(f"\n  💡 Recommendations:")
                if circ_rec > config.player_circularity_threshold:
                    print(f"    ⚠️  Consider increasing circularity threshold to {circ_rec:.2f}")
                else:
                    print(f"    ✅ Circularity threshold is appropriate")

    except Exception as e:
        print(f"\n❌ Error comparing with config: {e}")


def print_report(stats_by_type: Dict[str, ObjectStats], summary: Dict[str, Any]):
    """Print comprehensive analysis report."""

    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)

    print(f"\n📁 Files:")
    print(f"  Total images:              {summary['total_image_files']}")
    print(f"  Images with annotations:   {summary['total_annotation_files']}")
    print(f"  Images without annotations: {summary['images_without_annotations']}")
    print(f"    (Expected: player off-screen)")

    print(f"\n📊 Annotations:")
    print(f"  Total objects annotated:   {summary['total_annotations']}")
    print(f"  Files with player:         {summary['files_with_player']}")
    print(f"  Files with enemy:          {summary['files_with_enemy']}")
    print(f"  Object types found:        {', '.join(summary['object_types'])}")

    # Detailed statistics per object type
    for obj_type, stats_obj in sorted(stats_by_type.items()):
        stats = stats_obj.compute_statistics()

        print("\n" + "="*70)
        print(f"OBJECT TYPE: {obj_type.upper()}")
        print("="*70)

        print(f"\n  Count: {stats['count']} objects")

        # Position
        if 'position' in stats:
            pos = stats['position']
            print(f"\n  📍 Position Distribution:")
            print(f"    X: {pos['x']['min']}-{pos['x']['max']} (mean: {pos['x']['mean']:.1f}, std: {pos['x']['std']:.1f})")
            print(f"    Y: {pos['y']['min']}-{pos['y']['max']} (mean: {pos['y']['mean']:.1f}, std: {pos['y']['std']:.1f})")

        # HSV
        if 'hsv' in stats:
            hsv = stats['hsv']
            print(f"\n  🎨 HSV Color Ranges:")

            if 'hue' in hsv:
                h = hsv['hue']
                print(f"    H: {h['min']}-{h['max']} (mean: {h['mean']:.1f}, std: {h['std']:.1f})")
                print(f"       Recommended: {h['recommended_range'][0]}-{h['recommended_range'][1]} (mean±2σ)")

            if 'saturation' in hsv:
                s = hsv['saturation']
                print(f"    S: {s['min']}-{s['max']} (mean: {s['mean']:.1f}, std: {s['std']:.1f})")
                print(f"       Recommended: {s['recommended_range'][0]}-{s['recommended_range'][1]} (mean±2σ)")

            if 'value' in hsv:
                v = hsv['value']
                print(f"    V: {v['min']}-{v['max']} (mean: {v['mean']:.1f}, std: {v['std']:.1f})")
                print(f"       Recommended: {v['recommended_range'][0]}-{v['recommended_range'][1]} (mean±2σ)")

            # Consistency check
            if 'hue' in hsv and 'saturation' in hsv and 'value' in hsv:
                h_std = hsv['hue']['std']
                s_std = hsv['saturation']['std']
                v_std = hsv['value']['std']

                consistency = "Very consistent" if h_std < 5 and s_std < 10 and v_std < 10 else \
                             "Moderately consistent" if h_std < 10 and s_std < 20 and v_std < 20 else \
                             "Variable"

                print(f"\n    📊 Consistency: {consistency}")
                print(f"       (Hue std: {h_std:.1f}, Sat std: {s_std:.1f}, Val std: {v_std:.1f})")

        # Size
        if 'size' in stats:
            size = stats['size']
            print(f"\n  📏 Size Distribution:")

            if 'diameter' in size:
                d = size['diameter']
                print(f"    Diameter: {d['min']:.1f}-{d['max']:.1f}px (mean: {d['mean']:.1f}, std: {d['std']:.1f})")
                print(f"       Recommended: {d['recommended_range'][0]}-{d['recommended_range'][1]}px (mean±2σ)")

            if 'radius' in size:
                r = size['radius']
                print(f"    Radius:   {r['min']:.1f}-{r['max']:.1f}px (mean: {r['mean']:.1f}, std: {r['std']:.1f})")

        # Shape
        if 'shape' in stats:
            shape = stats['shape']
            print(f"\n  🔵 Shape Characteristics:")

            if 'circularity' in shape:
                c = shape['circularity']
                print(f"    Circularity: {c['min']:.2f}-{c['max']:.2f} (mean: {c['mean']:.2f}, std: {c['std']:.2f})")
                print(f"       Recommended threshold: ≥{c['recommended_threshold']:.2f} (mean-2σ)")

            if 'aspect_ratio' in shape:
                ar = shape['aspect_ratio']
                print(f"    Aspect ratio: {ar['min']:.2f}-{ar['max']:.2f} (mean: {ar['mean']:.2f}, std: {ar['std']:.2f})")

    print("\n" + "="*70)


def export_csv(stats_by_type: Dict[str, ObjectStats], output_path: Path):
    """Export statistics to CSV format."""
    import csv

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'object_type', 'count',
            'x_min', 'x_max', 'x_mean', 'x_std',
            'y_min', 'y_max', 'y_mean', 'y_std',
            'h_min', 'h_max', 'h_mean', 'h_std', 'h_rec_min', 'h_rec_max',
            's_min', 's_max', 's_mean', 's_std', 's_rec_min', 's_rec_max',
            'v_min', 'v_max', 'v_mean', 'v_std', 'v_rec_min', 'v_rec_max',
            'diameter_min', 'diameter_max', 'diameter_mean', 'diameter_std', 'diameter_rec_min', 'diameter_rec_max',
            'circularity_min', 'circularity_max', 'circularity_mean', 'circularity_std', 'circularity_rec_threshold'
        ])

        # Data rows
        for obj_type, stats_obj in stats_by_type.items():
            stats = stats_obj.compute_statistics()

            row = [obj_type, stats['count']]

            # Position
            if 'position' in stats:
                pos = stats['position']
                row.extend([
                    pos['x']['min'], pos['x']['max'], pos['x']['mean'], pos['x']['std'],
                    pos['y']['min'], pos['y']['max'], pos['y']['mean'], pos['y']['std']
                ])
            else:
                row.extend([''] * 8)

            # HSV
            if 'hsv' in stats:
                hsv = stats['hsv']
                for key in ['hue', 'saturation', 'value']:
                    if key in hsv:
                        row.extend([
                            hsv[key]['min'], hsv[key]['max'], hsv[key]['mean'], hsv[key]['std'],
                            hsv[key]['recommended_range'][0], hsv[key]['recommended_range'][1]
                        ])
                    else:
                        row.extend([''] * 6)
            else:
                row.extend([''] * 18)

            # Size
            if 'size' in stats and 'diameter' in stats['size']:
                d = stats['size']['diameter']
                row.extend([
                    d['min'], d['max'], d['mean'], d['std'],
                    d['recommended_range'][0], d['recommended_range'][1]
                ])
            else:
                row.extend([''] * 6)

            # Shape
            if 'shape' in stats and 'circularity' in stats['shape']:
                c = stats['shape']['circularity']
                row.extend([
                    c['min'], c['max'], c['mean'], c['std'],
                    c['recommended_threshold']
                ])
            else:
                row.extend([''] * 5)

            writer.writerow(row)

    print(f"\n✅ Exported statistics to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Analyze annotation files')
    parser.add_argument(
        '--samples-dir',
        type=Path,
        default=Path.home() / '.local/share/msmacro/calibration/minimap_samples',
        help='Directory containing samples and annotations'
    )
    parser.add_argument(
        '--export-csv',
        type=Path,
        help='Export statistics to CSV file'
    )
    args = parser.parse_args()

    if not args.samples_dir.exists():
        print(f"❌ Samples directory not found: {args.samples_dir}")
        return 1

    # Analyze annotations
    stats_by_type, summary = analyze_annotations(args.samples_dir)

    if not stats_by_type:
        print("\n❌ No annotations found!")
        print(f"   Expected location: {args.samples_dir}")
        print(f"   Looking for: *.annotations.json files")
        return 1

    # Print report
    print_report(stats_by_type, summary)

    # Compare with current config
    compare_with_current_config(stats_by_type)

    # Export CSV if requested
    if args.export_csv:
        export_csv(stats_by_type, args.export_csv)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(f"\n✅ Analyzed {summary['total_annotations']} annotations from {summary['total_annotation_files']} files")

    return 0


if __name__ == '__main__':
    sys.exit(main())
