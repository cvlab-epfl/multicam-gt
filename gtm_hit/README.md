# GTM Hit - Multi-View Annotation System

A Django application for crowdsourced annotation of 3D human poses in multi-camera video sequences.

## Overview

GTM Hit is a web-based annotation tool that allows workers to label 3D human poses across multiple synchronized camera views. The system projects 3D world coordinates onto 2D camera views, enabling precise annotation of human positions in complex multi-camera setups.

## Core Features

- **Multi-Camera Support**: Annotate across multiple synchronized camera views
- **3D-to-2D Projection**: Automatic projection of 3D world coordinates to 2D camera views
- **Worker Management**: Track annotation progress and generate validation codes
- **Frame Navigation**: Navigate through video sequences with customizable increments
- **Auto-alignment**: Automatic bounding box alignment using pose estimation models
- **Data Persistence**: Save and load annotations with database backend
- **ID Management**: Track and manage person identities across frames

## Architecture

### Models

- **Worker**: Manages annotation workers and their progress
- **Dataset**: Organizes annotation data by dataset
- **Person**: Represents individuals being annotated
- **MultiViewFrame**: Represents a specific frame across all camera views
- **Annotation**: Stores 3D world coordinates and object properties
- **Annotation2DView**: Stores 2D bounding boxes for each camera view
- **View**: Represents individual camera views
- **ValidationCode**: Generates unique codes for completed work

### Key Components

1. **Geometric Projection**: 3D world coordinates projected to 2D camera views
2. **Cuboid Generation**: 3D bounding boxes rendered as 2D rectangles
3. **Frame Management**: Sequential navigation through video sequences
4. **State Management**: Track worker progress through annotation workflow

## Workflow States

Workers progress through the following states:
- `-1`: Initial/Reset state
- `0`: Introduction/Index page
- `1`: Active annotation
- `2`: Completion/Finish
- `3`: Tutorial

## API Endpoints

### Core Annotation
- `click`: Create new 3D annotation from 2D click
- `action`: Update existing 3D annotation
- `save`: Persist annotations to database
- `load`: Retrieve annotations for a frame
- `changeframe`: Navigate between frames

### Worker Management
- `dispatch`: Route workers based on their current state
- `processInit`: Initialize worker session
- `processIndex`: Progress from introduction to tutorial
- `processTuto`: Progress from tutorial to annotation
- `processFrame`: Check completion criteria

### Advanced Features
- `merge`: Combine multiple annotations
- `changeid`: Modify person IDs with propagation
- `tracklet`: Track persons across frames
- `interpolate`: Generate intermediate annotations
- `auto_align_current`: Auto-align existing annotations

## Configuration

The system relies on Django settings for:
- Camera calibration parameters (`CALIBS`)
- Camera identifiers (`CAMS`)
- Frame paths and increments
- Ground plane settings (`FLAT_GROUND`)
- Object size defaults
- Mesh data for 3D projections

## Dependencies

- Django with PostgreSQL support
- NumPy for numerical computations
- Custom geometry utilities for 3D projections
- Multi-camera calibration data

## File Structure

```
gtm_hit/
├── models.py          # Database models
├── views.py           # Request handlers and business logic
├── urls.py            # URL routing
├── admin.py           # Django admin configuration
├── templates/         # HTML templates
├── static/            # Static assets
├── misc/              # Utility modules
│   ├── geometry.py    # 3D geometry utilities
│   ├── db.py          # Database utilities
│   ├── utils.py       # General utilities
│   └── serializer.py  # Data serialization
└── migrations/        # Database migrations
```

## Usage

1. Workers access the system via unique worker IDs
2. System dispatches workers to appropriate workflow state
3. Workers annotate 3D poses by clicking on 2D camera views
4. System automatically projects and validates 3D coordinates
5. Workers complete required number of frames to receive validation codes

## Development Notes

- The system supports both flat ground and mesh-based 3D projections
- Frame synchronization handles camera-specific timing offsets
- Bulk database operations optimize performance for large datasets
- Comprehensive error handling for geometric edge cases
