"""
Run once before launching the server.
Sets up the repository as required, establishing symlinks and...

For cvlab users:

python initial.py --dset_src '/cvlabdata2/cvlab/scout' --dsetname SCOUT
"""
from argparse import ArgumentParser
from pathlib import Path

def safe_symlink(source: Path, dest: Path):
    """
    Create a symlink from `dest` to `source`.
    If `dest` exists:
      - Do nothing if it's already a symlink to the correct source
      - Remove it if it's a wrong or broken symlink, or a file/directory
    """
    try:
        if dest.is_symlink():
            if dest.resolve() == source.resolve():
                print(f"[OK] Symlink already exists: {dest} -> {source}")
                return
            else:
                print(f"[FIX] Removing incorrect symlink: {dest}")
                dest.unlink()
        elif dest.exists():
            print(f"[WARN] Destination exists and is not a symlink: {dest}. Removing.")
            if dest.is_dir():
                # Use rmdir only if it's empty; otherwise you may want to raise an error
                dest.rmdir()
            else:
                dest.unlink()
        else:
            # Parent directory might not exist
            dest.parent.mkdir(parents=True, exist_ok=True)

        dest.symlink_to(source)
        print(f"[CREATED] Symlink: {dest} -> {source}")
    except Exception as e:
        print(f"[ERROR] Could not create symlink: {dest} -> {source}")
        print(f"        {e}")

def main():
    parser = ArgumentParser()
    parser.add_argument('--dset_src', type=str, required=True)
    parser.add_argument('--dsetname', type=str, default="SCOUT")
    parser.add_argument('--sequence', type=int, default=1, help="Sequence to annotate")
    args = parser.parse_args()

    SYMLINK_BASE = Path(args.dset_src).resolve()

    STATIC_ROOT = Path('gtm_hit/static')
    DSETPATH = STATIC_ROOT / "gtm_hit" / "dset" / args.dsetname
    DSETPATH.mkdir(parents=True, exist_ok=True)

    # 1. Symlink for frames (image sequence)
    src_images = SYMLINK_BASE / 'images' / f'sequence_{args.sequence}'
    dest_images = DSETPATH / "frames"
    safe_symlink(src_images, dest_images)

    # 2. Symlink for calibrations
    src_calibs = SYMLINK_BASE / 'calibrations'
    dest_calibs = DSETPATH / "calibrations"
    safe_symlink(src_calibs, dest_calibs)

    # 3. Symlink for mesh
    src_mesh = SYMLINK_BASE / 'meshes'
    dest_mesh = DSETPATH / 'meshes'
    dest_mesh.parent.mkdir(parents=True, exist_ok=True)
    safe_symlink(src_mesh, dest_mesh)

    src_roi = SYMLINK_BASE / 'roi'
    dest_roi = (DSETPATH / 'roi')
    dest_roi.parent.mkdir(parents=True, exist_ok=True)
    safe_symlink(src_roi, dest_roi)

    src_annotation = SYMLINK_BASE / 'annotations' / 'raw' / f'annotations_sequence_{args.sequence}_raw.json'
    dest_annotation = (DSETPATH / 'annotation' / 'annotations.json')
    dest_annotation.parent.mkdir(parents=True, exist_ok=True)
    safe_symlink(src_annotation, dest_annotation)

if __name__ == '__main__':
    main()
