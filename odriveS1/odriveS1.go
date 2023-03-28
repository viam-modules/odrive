package main

import (
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"

	"github.com/edaniels/golog"
	"github.com/pkg/errors"
	goutils "go.viam.com/utils"

	"go.viam.com/rdk/components/generic"
	"go.viam.com/rdk/components/motor"
	"go.viam.com/rdk/config"
	"go.viam.com/rdk/module"
	"go.viam.com/rdk/registry"
	"go.viam.com/rdk/resource"
)

var model = resource.NewModel("viamlabs", "motor", "odriveS1")

type OdriveConfig struct {
	SerialNumber     float64 `json:"serial_number,omitmepty"`
	MaxRPM           float64 `json:"max_rpm"`
	OdriveConfigFile string  `json:"odrive_config_file,omitempty"`
}

type OdriveS1 struct {
	name   string
	cancel func()
	logger golog.Logger

	// generic.Unimplemented is a helper that embeds an unimplemented error in the Do method.
	generic.Unimplemented

	// offset keeps track of the difference between the user specified 0 position (changed through reset_zero_position) and the encoder 0 position.
	offset            float64
	serialNumber      string
	maxRPM            float64
	positionReporting bool
}

func main() {
	goutils.ContextualMain(mainWithArgs, golog.NewDevelopmentLogger("odriveMotorModule"))
}

func mainWithArgs(ctx context.Context, args []string, logger golog.Logger) (err error) {
	registerOdrive(logger)
	modalModule, err := module.NewModuleFromArgs(ctx, logger)

	if err != nil {
		return err
	}
	modalModule.AddModelFromRegistry(ctx, motor.Subtype, model)

	err = modalModule.Start(ctx)
	defer modalModule.Close(ctx)

	if err != nil {
		return err
	}
	<-ctx.Done()
	return nil
}

// helper function to add the base's constructor and metadata to the component registry, so that we can later construct it.
func registerOdrive(logger golog.Logger) {
	registry.RegisterComponent(
		motor.Subtype,
		model,
		registry.Component{Constructor: func(
			ctx context.Context,
			deps registry.Dependencies,
			config config.Component,
			logger golog.Logger,
		) (interface{}, error) {
			return newOdrive(config, logger)
		}})
}

func newOdrive(rawConfig config.Component, logger golog.Logger) (motor.Motor, error) {
	_, cancel := context.WithCancel(context.Background())
	odrive := &OdriveS1{
		name:   rawConfig.Name,
		cancel: cancel,
		logger: logger,
	}
	// TODO: Replace config extraction with ConvertedAttributes
	serialNumber, ok := rawConfig.Attributes["serial_number"]
	if ok {
		odrive.serialNumber = serialNumber.(string)
	} else {
		logger.Warn("No serial number provided for the odrive. Using any odrive that is connected")
	}
	maxRPM, ok := rawConfig.Attributes["max_rpm"]
	if !ok {
		return nil, errors.New("Must provide a max_rpm for motors controlled by an odrive")
	}
	odrive.maxRPM = maxRPM.(float64)

	if odriveConfigFile, ok := rawConfig.Attributes["odrive_config_file"].(string); ok {
		exec.Command("python3", "odrivetool", "restore-config", odriveConfigFile).Run()
	}

	return odrive, nil
}

// Position returns motor position in rotations.
func (m *OdriveS1) Position(ctx context.Context, extra map[string]interface{}) (float64, error) {
	cmd := exec.Command("python3",
		"../OdriveS1.py",
		"--serial-number",
		fmt.Sprintf("%s", m.serialNumber),
		"--get-position",
		"--offset",
		fmt.Sprintf("%f", m.offset))

	output, err := cmd.Output()
	if err != nil {
		return 0, err
	}

	pos, err := m.Float64frombytes(output)
	if err != nil {
		return 0, err
	}
	return pos, nil
}

// Properties returns the status of whether the motor supports certain optional features.
func (m *OdriveS1) Properties(ctx context.Context, extra map[string]interface{}) (map[motor.Feature]bool, error) {
	return map[motor.Feature]bool{
		motor.PositionReporting: true,
	}, nil
}

// SetPower sets the given power percentage.
func (m *OdriveS1) SetPower(ctx context.Context, powerPct float64, extra map[string]interface{}) error {
	cmd := exec.Command("python3",
		"../OdriveS1.py",
		"--serial-number",
		fmt.Sprintf("%s", m.serialNumber),
		"--set-power",
		"--max-rpm",
		fmt.Sprintf("%f", m.maxRPM),
		"--power",
		fmt.Sprintf("%f", powerPct))

	output, err := cmd.Output()
	if err != nil {
		return err
	}

	outputStr := fmt.Sprintf("%s", output)
	if outputStr != "" {
		m.logger.Error(fmt.Sprintf("%s", output))
	}

	return nil
}

// GoFor sets the given direction and an arbitrary power percentage.
func (m *OdriveS1) GoFor(ctx context.Context, rpm, revolutions float64, extra map[string]interface{}) error {
	cmd := exec.Command("python3",
		"../OdriveS1.py",
		"--serial-number",
		fmt.Sprintf("%s", m.serialNumber),
		"--go-for",
		"--rpm",
		fmt.Sprintf("%f", rpm),
		"--revolutions",
		fmt.Sprintf("%f", revolutions),
		"--offset",
		fmt.Sprintf("%f", m.offset))

	output, err := cmd.Output()
	if err != nil {
		return err
	}

	outputStr := fmt.Sprintf("%s", output)
	if outputStr != "" {
		m.logger.Error(fmt.Sprintf("%s", output))
	}

	return nil
}

// GoTo sets the given direction and an arbitrary power percentage for now.
func (m *OdriveS1) GoTo(ctx context.Context, rpm, pos float64, extra map[string]interface{}) error {
	cmd := exec.Command("python3",
		"../OdriveS1.py",
		"--serial-number",
		fmt.Sprintf("%s", m.serialNumber),
		"--go-to",
		"--rpm",
		fmt.Sprintf("%f", rpm),
		"--revolutions",
		fmt.Sprintf("%f", pos),
		"--offset",
		fmt.Sprintf("%f", m.offset))

	output, err := cmd.Output()
	if err != nil {
		return err
	}

	outputStr := fmt.Sprintf("%s", output)
	if outputStr != "" {
		m.logger.Error(fmt.Sprintf("%s", output))
	}

	return nil
}

// ResetZeroPosition
func (m *OdriveS1) ResetZeroPosition(ctx context.Context, offset float64, extra map[string]interface{}) error {
	pos, err := m.Position(ctx, make(map[string]interface{}))
	if err != nil {
		return err
	}
	m.offset += pos
	return nil
}

// Stop
func (m *OdriveS1) Stop(ctx context.Context, extra map[string]interface{}) error {
	cmd := exec.Command("python3",
		"../OdriveS1.py",
		"--serial-number",
		fmt.Sprintf("%s", m.serialNumber),
		"--stop")

	output, err := cmd.Output()
	if err != nil {
		return err
	}

	outputStr := fmt.Sprintf("%s", output)
	if outputStr != "" {
		m.logger.Error(fmt.Sprintf("%s", output))
	}

	return nil
}

// IsPowered returns if the motor is pretending to be on or not, and its power level.
func (m *OdriveS1) IsPowered(ctx context.Context, extra map[string]interface{}) (bool, float64, error) {
	cmd := exec.Command("python3",
		"../OdriveS1.py",
		"--serial-number",
		fmt.Sprintf("%s", m.serialNumber),
		"--is-powered",
		"--max-rpm",
		fmt.Sprintf("%f", m.maxRPM))

	output, err := cmd.Output()
	if err != nil {
		return false, 0, err
	}

	outputString := strings.ReplaceAll(fmt.Sprintf("%s", output), "\n", "")
	outputSlice := strings.Split(outputString, " ")

	isPowered := outputSlice[0] == "True"

	power, err := strconv.ParseFloat(outputSlice[1], 64)
	if err != nil {
		m.logger.Error(fmt.Sprintf("%s", output))
		return false, 0, err
	}

	return isPowered, power, nil
}

// IsMoving returns if the motor is pretending to be moving or not.
func (m *OdriveS1) IsMoving(ctx context.Context) (bool, error) {
	cmd := exec.Command("python3",
		"../OdriveS1.py",
		"--serial-number",
		fmt.Sprintf("%s", m.serialNumber),
		"--is-moving")

	output, err := cmd.Output()
	if err != nil {
		return false, err
	}

	outputString := strings.ReplaceAll(fmt.Sprintf("%s", output), "\n", "")
	isMoving := outputString == "True"

	if !isMoving && outputString != "False" {
		m.logger.Error(fmt.Sprintf("%s", output))
	}

	return isMoving, nil
}

func (m *OdriveS1) Float64frombytes(bytes []byte) (float64, error) {
	text := strings.ReplaceAll(fmt.Sprintf("%s", bytes), "\n", "")
	float, err := strconv.ParseFloat(text, 64)
	if err != nil {
		m.logger.Error(fmt.Sprintf("%s", text))
		return 0, err
	}
	return float, nil
}
