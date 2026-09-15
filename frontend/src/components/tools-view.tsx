import {
  Atom,
  Beaker,
  Calculator,
  ChartSpline,
  FlaskConical,
  Ruler,
} from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { RankWiseApi } from "@/api/client";
import type { CapabilityMap, ToolResult } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const MATH_OPERATIONS = [
  ["simplify", "Simplify"],
  ["compare", "Compare"],
  ["differentiate", "Differentiate"],
  ["integrate", "Integrate"],
  ["solve", "Solve"],
] as const;

function ToolCard({
  icon,
  title,
  description,
  available,
  children,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  available: boolean;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex gap-3">
            <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
              {icon}
            </div>
            <div>
              <CardTitle className="text-sm">{title}</CardTitle>
              <CardDescription className="mt-1">{description}</CardDescription>
            </div>
          </div>
          <Badge variant={available ? "success" : "warning"}>
            {available ? "Available" : "Offline"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Result({ value }: { value: ToolResult | null }) {
  if (!value) return null;
  return (
    <pre className="result-json mt-4">{JSON.stringify(value, null, 2)}</pre>
  );
}

export function ToolsView({
  api,
  capabilities,
}: {
  api: RankWiseApi;
  capabilities: CapabilityMap;
}) {
  const [mathOperation, setMathOperation] = useState("simplify");
  const [expression, setExpression] = useState("(x + 1)^2");
  const [otherExpression, setOtherExpression] = useState("x^2 + 2*x + 1");
  const [mathResult, setMathResult] = useState<ToolResult | null>(null);
  const [mathLoading, setMathLoading] = useState(false);

  const [unitValue, setUnitValue] = useState("1000");
  const [fromUnit, setFromUnit] = useState("meter");
  const [toUnit, setToUnit] = useState("kilometer");
  const [unitResult, setUnitResult] = useState<ToolResult | null>(null);
  const [unitLoading, setUnitLoading] = useState(false);

  const [plotExpression, setPlotExpression] = useState("sin(x)");
  const [plotUrl, setPlotUrl] = useState<string | null>(null);
  const [plotLoading, setPlotLoading] = useState(false);

  const [equation, setEquation] = useState("CH4 + O2 -> CO2 + H2O");
  const [balanceResult, setBalanceResult] = useState<ToolResult | null>(null);
  const [balanceLoading, setBalanceLoading] = useState(false);

  const [notation, setNotation] = useState("CCO");
  const [notationFormat, setNotationFormat] = useState<"smiles" | "inchi">(
    "smiles",
  );
  const [moleculeResult, setMoleculeResult] = useState<ToolResult | null>(null);
  const [moleculeLoading, setMoleculeLoading] = useState(false);

  const [lookup, setLookup] = useState("ethanol");
  const [lookupConsent, setLookupConsent] = useState(false);
  const [lookupResult, setLookupResult] = useState<ToolResult | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);

  useEffect(() => {
    return () => {
      if (plotUrl) URL.revokeObjectURL(plotUrl);
    };
  }, [plotUrl]);

  const run = async (
    action: () => Promise<ToolResult>,
    setLoading: (value: boolean) => void,
    setResult: (value: ToolResult) => void,
  ) => {
    setLoading(true);
    try {
      setResult(await action());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Tool call failed");
    } finally {
      setLoading(false);
    }
  };

  const submitMath = (event: FormEvent) => {
    event.preventDefault();
    const body: Record<string, unknown> = {
      operation: mathOperation,
      expression,
      variables: ["x"],
      variable: "x",
    };
    if (mathOperation === "compare") body.other_expression = otherExpression;
    void run(() => api.symbolicMath(body), setMathLoading, setMathResult);
  };

  const submitUnits = (event: FormEvent) => {
    event.preventDefault();
    const value = Number(unitValue);
    if (!Number.isFinite(value)) {
      toast.error("Enter a finite numeric value");
      return;
    }
    void run(
      () => api.convertUnits({ value, from_unit: fromUnit, to_unit: toUnit }),
      setUnitLoading,
      setUnitResult,
    );
  };

  const submitPlot = async (event: FormEvent) => {
    event.preventDefault();
    setPlotLoading(true);
    try {
      const blob = await api.plot({
        expression: plotExpression,
        variable: "x",
        start: -10,
        end: 10,
        samples: 500,
      });
      setPlotUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return URL.createObjectURL(blob);
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Plot failed");
    } finally {
      setPlotLoading(false);
    }
  };

  return (
    <Tabs defaultValue="quantitative">
      <TabsList>
        <TabsTrigger value="quantitative">Math & physics</TabsTrigger>
        <TabsTrigger value="chemistry">Chemistry</TabsTrigger>
      </TabsList>

      <TabsContent value="quantitative">
        <div className="grid gap-5 lg:grid-cols-2">
          <ToolCard
            icon={<Calculator className="size-4" />}
            title="Symbolic mathematics"
            description="Simplify, compare, differentiate, integrate, or solve a bounded expression."
            available={capabilities.symbolic_math}
          >
            <form onSubmit={submitMath} className="grid gap-3">
              <div className="grid grid-cols-[150px_1fr] gap-3">
                <Select value={mathOperation} onValueChange={setMathOperation}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MATH_OPERATIONS.map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  value={expression}
                  onChange={(event) => setExpression(event.target.value)}
                />
              </div>
              {mathOperation === "compare" && (
                <Input
                  value={otherExpression}
                  aria-label="Other expression"
                  onChange={(event) => setOtherExpression(event.target.value)}
                />
              )}
              <Button
                type="submit"
                className="w-fit"
                disabled={mathLoading || !capabilities.symbolic_math}
              >
                {mathLoading && <Spinner />} Run calculation
              </Button>
            </form>
            <Result value={mathResult} />
          </ToolCard>

          <ToolCard
            icon={<Ruler className="size-4" />}
            title="Unit conversion"
            description="Convert compatible units with dimensional validation from Pint."
            available={capabilities.unit_conversion}
          >
            <form onSubmit={submitUnits} className="grid gap-3">
              <div className="grid grid-cols-3 gap-2">
                <Input
                  aria-label="Value"
                  value={unitValue}
                  onChange={(event) => setUnitValue(event.target.value)}
                />
                <Input
                  aria-label="From unit"
                  value={fromUnit}
                  onChange={(event) => setFromUnit(event.target.value)}
                />
                <Input
                  aria-label="To unit"
                  value={toUnit}
                  onChange={(event) => setToUnit(event.target.value)}
                />
              </div>
              <Button
                type="submit"
                className="w-fit"
                disabled={unitLoading || !capabilities.unit_conversion}
              >
                {unitLoading && <Spinner />} Convert
              </Button>
            </form>
            <Result value={unitResult} />
          </ToolCard>

          <ToolCard
            icon={<ChartSpline className="size-4" />}
            title="Function plot"
            description="Render a bounded single-variable function over x = −10…10."
            available={capabilities.plotting}
          >
            <form onSubmit={submitPlot} className="flex gap-2">
              <Input
                value={plotExpression}
                onChange={(event) => setPlotExpression(event.target.value)}
              />
              <Button
                type="submit"
                disabled={plotLoading || !capabilities.plotting}
              >
                {plotLoading && <Spinner />} Plot
              </Button>
            </form>
            {plotUrl && (
              <img
                src={plotUrl}
                alt={`Plot of ${plotExpression}`}
                className="mt-4 w-full rounded-lg border"
              />
            )}
          </ToolCard>
        </div>
      </TabsContent>

      <TabsContent value="chemistry">
        <div className="grid gap-5 lg:grid-cols-2">
          <ToolCard
            icon={<FlaskConical className="size-4" />}
            title="Balance reaction"
            description="Derive coefficients and independently verify atom and charge conservation."
            available={capabilities.reaction_balancing}
          >
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () => api.balanceEquation(equation),
                  setBalanceLoading,
                  setBalanceResult,
                );
              }}
              className="flex gap-2"
            >
              <Input
                value={equation}
                onChange={(event) => setEquation(event.target.value)}
              />
              <Button
                type="submit"
                disabled={balanceLoading || !capabilities.reaction_balancing}
              >
                {balanceLoading && <Spinner />} Verify
              </Button>
            </form>
            <Result value={balanceResult} />
          </ToolCard>

          <ToolCard
            icon={<Atom className="size-4" />}
            title="Analyze molecule"
            description="Validate a structure and calculate canonical identifiers and descriptors."
            available={capabilities.molecule_analysis}
          >
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () => api.analyzeMolecule(notation, notationFormat),
                  setMoleculeLoading,
                  setMoleculeResult,
                );
              }}
              className="grid gap-3"
            >
              <div className="grid grid-cols-[120px_1fr] gap-2">
                <Select
                  value={notationFormat}
                  onValueChange={(value) =>
                    setNotationFormat(value as "smiles" | "inchi")
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="smiles">SMILES</SelectItem>
                    <SelectItem value="inchi">InChI</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  value={notation}
                  onChange={(event) => setNotation(event.target.value)}
                />
              </div>
              <Button
                type="submit"
                className="w-fit"
                disabled={moleculeLoading || !capabilities.molecule_analysis}
              >
                {moleculeLoading && <Spinner />} Analyze
              </Button>
            </form>
            <Result value={moleculeResult} />
          </ToolCard>

          <ToolCard
            icon={<Beaker className="size-4" />}
            title="External chemical lookup"
            description="Fetch optional PubChem properties with source, timestamp, and cache provenance."
            available={capabilities.external_chemical_lookup}
          >
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () => api.lookupChemical(lookup, lookupConsent),
                  setLookupLoading,
                  setLookupResult,
                );
              }}
              className="grid gap-3"
            >
              <div className="flex gap-2">
                <Input
                  value={lookup}
                  onChange={(event) => setLookup(event.target.value)}
                />
                <Button
                  type="submit"
                  disabled={
                    lookupLoading ||
                    !lookupConsent ||
                    !capabilities.external_chemical_lookup
                  }
                >
                  {lookupLoading && <Spinner />} Look up
                </Button>
              </div>
              <Label className="flex items-start gap-2 text-xs font-normal leading-5 text-muted-foreground">
                <input
                  type="checkbox"
                  className="mt-1 accent-[#3659e3]"
                  checked={lookupConsent}
                  onChange={(event) => setLookupConsent(event.target.checked)}
                />
                I consent to send this compound name to PubChem. Results are
                external enrichment, not evidence from my uploaded sources.
              </Label>
            </form>
            {lookupResult && (
              <div className="mt-4">
                <Badge variant="warning">External enrichment</Badge>
                <Result value={lookupResult} />
              </div>
            )}
          </ToolCard>
        </div>
      </TabsContent>
    </Tabs>
  );
}
