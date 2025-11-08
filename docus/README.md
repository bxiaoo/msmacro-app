# MSMacro Documentation

## Recent Updates

**2025-11-08 - Object Detection v3.1 Enhancements**:
- ✅ **Truly lossless calibration**: Raw minimap capture before JPEG compression (eliminates color artifacts)
- ✅ **Full detection visualization**: Backend-rendered overlays showing player + all other players with precise positions
- ✅ **New API endpoints**: `/api/cv/raw-minimap` (lossless), `/api/cv/detection-preview` (visualization)
- ✅ **Enhanced debugging**: Positions array for other players, improved UI with full-width previews

See `08_OBJECT_DETECTION.md` for detailed changes and migration guide.

---

## User Documentation

Main documentation files for users and operators:

- **00_OVERVIEW.md** - Project overview and introduction
- **01_ARCHITECTURE.md** - System architecture and components
- **02_USAGE.md** - Usage guide and basic operations
- **03_CONFIGURATION.md** - Configuration options and environment variables
- **04_DETECTION_ALGORITHM.md** - CV detection algorithm details
- **05_API_REFERENCE.md** - REST API reference
- **06_MAP_CONFIGURATION.md** - Map configuration user guide
- **07_SYSTEM_MONITORING.md** - System stats and performance monitoring
- **08_OBJECT_DETECTION.md** - Minimap object detection (player/other players)
- **09_DATA_FLOW.md** - Complete data flow diagrams (frontend ↔ backend)

## Testing Documentation

Testing guides and procedures (for development/QA):

- **testing/MAP_CONFIG_TESTING_GUIDE.md** - Manual testing guide for map configuration
- **testing/MAP_CONFIG_FIX_SUMMARY.md** - Map configuration logic fix summary
- **testing/SYSTEM_STATS_IMPLEMENTATION.md** - System stats implementation notes
- **testing/OBJECT_DETECTION_IMPLEMENTATION_PLAN.md** - Object detection 4-phase plan

## Archived Documentation

Historical implementation notes and technical details (archived for reference):

- **archived/CV_CONFIGURATION_SYSTEM.md** - CV configuration system implementation
- **archived/CV_PERFORMANCE_OPTIMIZATION_IMPLEMENTATION.md** - Performance optimization notes
- **archived/FRONTEND_IMPLEMENTATION.md** - Frontend implementation details
- **archived/REALTIME_PREVIEW_IMPLEMENTATION.md** - Real-time preview implementation
- **archived/YUYV_DETECTION_IMPLEMENTATION.md** - YUYV detection implementation

## Document Status

- **Active**: User documentation (00-07 series) - kept up to date
- **Testing**: Testing guides - used during QA and deployment
- **Archived**: Implementation notes - historical reference only

## Contributing

When adding new documentation:
- User-facing docs → Root level (numbered series)
- Testing procedures → `testing/` directory
- Implementation notes → `archived/` directory (if still relevant) or delete

---

Last updated: 2025-11-08
