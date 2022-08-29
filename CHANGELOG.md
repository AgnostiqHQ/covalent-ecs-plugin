# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [UNRELEASED]

### Tests

- Enabled Codecov

## [0.11.0] - 2022-08-25

### Changed

- Changed covalent version in templated Dockerfile to correspond to 0.177.0

### Tests

- Added remaining unit tests for the `ecs.py` module.

## [0.10.0] - 2022-08-19

### Changed

- Updated s3 client to initilize with explicit profile name

## [0.9.0] - 2022-08-18

### Added

- Unit tests for the `ecs.py` module.

## [0.8.0] - 2022-08-17

### Changed

- Pinned `covalent` version to `stable`

## [0.7.0] - 2022-08-16

### Changed

- Updated required `covalent` version

## [0.6.2] - 2022-08-13

### Fixed

- Fixed tests output

## [0.6.1] - 2022-08-13

### Fixed

- Fixed release trigger

## [0.6.0] - 2022-08-12

### Added

- Manifest file

## [0.5.0] - 2022-08-12

### Added

- Workflow actions to support releases

### Changed

- Changed from alpha to beta

## [0.4.0] - 2022-08-09

### Changed

- README.md file to include correct instructions on how to use the ECS executor.

## [0.3.0] - 2022-08-09

### Added

- Unit tests for constructing python execution and dockerfile methods.

### Fixed

- ECS Executor.

## [0.2.0] - 2022-08-04

### Added

- Testing CICD pipeline

### Changed

- Pre-commit install script.
- Some references of Fargate were changed to ECS.

## [0.1.0] - 2022-03-31

### Changed

- Changed global variable executor_plugin_name -> EXECUTOR_PLUGIN_NAME in executors to conform with PEP8.
