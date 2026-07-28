import { Search } from "lucide-react";

type SelectFilter = {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
};

export function FilterBar({
  searchLabel,
  searchValue,
  onSearchChange,
  selectLabel,
  selectValue,
  selectOptions,
  onSelectChange,
  additionalSelects = []
}: {
  searchLabel: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  selectLabel?: string;
  selectValue?: string;
  selectOptions?: string[];
  onSelectChange?: (value: string) => void;
  additionalSelects?: SelectFilter[];
}) {
  const selects: SelectFilter[] = [
    ...(selectLabel && selectOptions && onSelectChange
      ? [{ label: selectLabel, value: selectValue || selectOptions[0] || "", options: selectOptions, onChange: onSelectChange }]
      : []),
    ...additionalSelects
  ];

  return (
    <div className="filter-bar">
      <label className="search-control">
        <Search size={17} aria-hidden />
        <span className="sr-only">{searchLabel}</span>
        <input
          type="search"
          aria-label={searchLabel}
          placeholder={searchLabel}
          value={searchValue}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
      {selects.length ? <div className="filter-bar__selects">{selects.map((select) => (
        <label className="select-control" key={select.label}>
          <span>{select.label}</span>
          <select aria-label={select.label} value={select.value} onChange={(event) => select.onChange(event.target.value)}>
            {select.options.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
      ))}</div> : null}
    </div>
  );
}
