package main

import (
	"strings"
	"testing"
)

func TestDockerArgsEnforceIsolationAndContainNoSource(t *testing.T) {
	s := &server{runtime: "runsc", image: "sandbox:test"}
	args := strings.Join(s.dockerArgs("job-1"), " ")
	for _, required := range []string{"--runtime runsc", "--network none", "--read-only", "--memory 128m", "--pids-limit 32", "--cap-drop ALL", "no-new-privileges", "--user 65534:65534"} {
		if !strings.Contains(args, required) {
			t.Errorf("missing %q in %s", required, args)
		}
	}
	if strings.Contains(args, "print(") {
		t.Fatal("source must never appear in process arguments")
	}
}

func TestValidationFailsClosed(t *testing.T) {
	valid := runRequest{Language: "python", Code: "print(1)", TimeoutSeconds: 8, ReadOnly: true, MemoryMB: 128, CPUSeconds: 2, Pids: 32}
	if validate(valid) != nil {
		t.Fatal("valid fixed policy rejected")
	}
	valid.Network = true
	if validate(valid) == nil {
		t.Fatal("network-enabled request accepted")
	}
}

func TestCappedBuffer(t *testing.T) {
	b := &cappedBuffer{limit: 4}
	n, _ := b.Write([]byte("123456"))
	if n != 6 || b.String() != "1234" {
		t.Fatalf("unexpected cap result: n=%d value=%q", n, b.String())
	}
}
