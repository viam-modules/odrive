package main

import (
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"

	"github.com/edaniels/golog"
	goutils "go.viam.com/utils"

	"go.viam.com/rdk/components/generic"
	"go.viam.com/rdk/components/motor"
	"go.viam.com/rdk/config"
	"go.viam.com/rdk/module"
	"go.viam.com/rdk/registry"
	"go.viam.com/rdk/resource"
)

var model = resource.NewModel("viamlabs", "motor", "odriveS1")

func main() {
	goutils.ContextualMain(mainWithArgs, golog.NewDevelopmentLogger("odriveMotorModule"))
}

func mainWithArgs(ctx context.Context, args []string, logger golog.Logger) (err error) {
	registerMotor()
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
func registerMotor() {
	registry.RegisterComponent(
		motor.Subtype, // the "base" API: "rdk:component:base"
		model,
		registry.Component{Constructor: func(
			ctx context.Context,
			deps registry.Dependencies,
			config config.Component,
			logger golog.Logger,
		) (interface{}, error) {
			return newMotor(config.Name, logger)
		}})
}

func newMotor(name string, logger golog.Logger) (motor.Motor, error) {
	_, cancel := context.WithCancel(context.Background())
	odrive := &OdriveS1{
		name:   name,
		cancel: cancel,
		logger: logger,
	}
	return odrive, nil
}

type OdriveS1 struct {
	name              string
	cancel            func()
	logger            golog.Logger
	PositionReporting bool

	// generic.Unimplemented is a helper that embeds an unimplemented error in the Do method.
	generic.Unimplemented
}

// Position returns motor position in rotations.
func (m *OdriveS1) Position(ctx context.Context, extra map[string]interface{}) (float64, error) {
	cmd := exec.Command("python3", "../OdriveS1.py", "--get-position", "--max-rpm", "10", "--max-velocity", "10")

	position, err := cmd.Output()
	if err != nil {
		return 0, err
	}

	pos, err := m.Float64frombytes(position)
	if err != nil {
		return 0, err
	}
	return pos, nil
}

// Properties returns the status of whether the motor supports certain optional features.
func (m *OdriveS1) Properties(ctx context.Context, extra map[string]interface{}) (map[motor.Feature]bool, error) {
	return map[motor.Feature]bool{
		motor.PositionReporting: m.PositionReporting,
	}, nil
}

// SetPower sets the given power percentage.
func (m *OdriveS1) SetPower(ctx context.Context, powerPct float64, extra map[string]interface{}) error {
	cmd := exec.Command("python3", "../OdriveS1.py", "--set-power", "--max-rpm", "600", "--max-velocity", "10", "--power", ".15")

	_, err := cmd.Output()
	if err != nil {
		return err
	}
	return nil
}

// GoFor sets the given direction and an arbitrary power percentage.
func (m *OdriveS1) GoFor(ctx context.Context, rpm, revolutions float64, extra map[string]interface{}) error {
	return nil
}

// GoTo sets the given direction and an arbitrary power percentage for now.
func (m *OdriveS1) GoTo(ctx context.Context, rpm, pos float64, extra map[string]interface{}) error {
	return nil
}

// ResetZeroPosition
func (m *OdriveS1) ResetZeroPosition(ctx context.Context, offset float64, extra map[string]interface{}) error {
	return nil
}

// Stop
func (m *OdriveS1) Stop(ctx context.Context, extra map[string]interface{}) error {
	cmd := exec.Command("python3", "../OdriveS1.py", "--stop", "--max-rpm", "10", "--max-velocity", "10")

	_, err := cmd.Output()
	if err != nil {
		return err
	}
	return nil
}

// IsPowered returns if the motor is pretending to be on or not, and its power level.
func (m *OdriveS1) IsPowered(ctx context.Context, extra map[string]interface{}) (bool, float64, error) {
	cmd := exec.Command("python3", "../OdriveS1.py", "--is-powered", "--max-rpm", "10", "--max-velocity", "10")

	output, err := cmd.Output()
	if err != nil {
		return false, 0, err
	}

	outputString := strings.ReplaceAll(fmt.Sprintf("%s", output), "\n", "")
	outputSlice := strings.Split(outputString, " ")

	isPowered := outputSlice[0] == "True"

	power, err := strconv.ParseFloat(outputSlice[1], 64)
	if err != nil {
		return false, 0, err
	}

	return isPowered, power, nil
}

// IsMoving returns if the motor is pretending to be moving or not.
func (m *OdriveS1) IsMoving(ctx context.Context) (bool, error) {
	cmd := exec.Command("python3", "../OdriveS1.py", "--is-moving", "--max-rpm", "10", "--max-velocity", "10")

	output, err := cmd.Output()
	if err != nil {
		return false, err
	}

	outputString := strings.ReplaceAll(fmt.Sprintf("%s", output), "\n", "")
	isMoving := outputString == "True"

	return isMoving, nil
}

func (m *OdriveS1) Float64frombytes(bytes []byte) (float64, error) {
	text := strings.ReplaceAll(fmt.Sprintf("%s", bytes), "\n", "")
	float, err := strconv.ParseFloat(text, 64)
	if err != nil {
		return 0, err
	}
	return float, nil
}
